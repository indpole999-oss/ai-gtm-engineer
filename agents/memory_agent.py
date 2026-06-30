"""
Memory Agent - Short-term, long-term, and vector memory management
Steps 71-77: Conversation memory, company/contact history, semantic search
Supports in-memory (default), Redis, PostgreSQL, and ChromaDB/Pinecone vector stores
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Memory backend config
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "local")  # local | redis | postgres
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Vector store config
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "chroma")  # chroma | pinecone | pgvector
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "gtm-memory")

# Embeddings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


class MemoryAgent:
  """Manages short-term conversation memory, long-term company/contact history, and vector search"""

  def __init__(self):
    self.backend = MEMORY_BACKEND
    self.vector_backend = VECTOR_BACKEND
    # In-memory fallback stores
    self._short_term: Dict[str, List[Dict]] = {}   # session_id -> messages
    self._long_term: Dict[str, Dict] = {}          # entity_key -> data
    self._redis = None
    self._chroma_client = None
    self._chroma_collection = None

  # ── Short-Term Memory (per session conversation history) ─────────────────

  def add_message(self, session_id: str, role: str, content: str) -> None:
    """Add a message to short-term conversation memory"""
    if session_id not in self._short_term:
      self._short_term[session_id] = []
    self._short_term[session_id].append({
      "role": role,
      "content": content,
      "timestamp": datetime.utcnow().isoformat()
    })
    # Keep last 20 messages per session
    if len(self._short_term[session_id]) > 20:
      self._short_term[session_id] = self._short_term[session_id][-20:]

  def get_conversation(self, session_id: str) -> List[Dict]:
    """Get conversation history for a session (OpenAI message format)"""
    messages = self._short_term.get(session_id, [])
    return [{"role": m["role"], "content": m["content"]} for m in messages]

  def clear_conversation(self, session_id: str) -> None:
    """Clear short-term memory for a session"""
    self._short_term.pop(session_id, None)

  # ── Long-Term Memory (company/contact research cache) ────────────────────

  def store(self, entity_type: str, entity_id: str, data: Dict) -> None:
    """Store entity data in long-term memory (company, contact, campaign)"""
    key = f"{entity_type}:{entity_id}"
    self._long_term[key] = {
      **data,
      "_stored_at": datetime.utcnow().isoformat(),
      "_entity_type": entity_type,
      "_entity_id": entity_id
    }
    logger.debug(f"Stored {key} in long-term memory")

  def recall(self, entity_type: str, entity_id: str) -> Optional[Dict]:
    """Retrieve entity data from long-term memory"""
    key = f"{entity_type}:{entity_id}"
    return self._long_term.get(key)

  def list_entities(self, entity_type: str) -> List[Dict]:
    """List all stored entities of a given type"""
    return [
      v for k, v in self._long_term.items()
      if k.startswith(f"{entity_type}:")
    ]

  def update_company_research(self, domain: str, research: Dict) -> None:
    """Store company research results"""
    self.store("company", domain, research)

  def get_company_research(self, domain: str) -> Optional[Dict]:
    """Retrieve cached company research"""
    return self.recall("company", domain)

  def update_contact(self, email: str, contact_data: Dict) -> None:
    """Store contact enrichment data"""
    self.store("contact", email, contact_data)

  def get_contact(self, email: str) -> Optional[Dict]:
    """Retrieve cached contact data"""
    return self.recall("contact", email)

  def log_outreach(self, email: str, outreach_data: Dict) -> None:
    """Log outreach activity for a contact"""
    key = f"outreach:{email}"
    existing = self._long_term.get(key, {"history": []})
    existing["history"].append({
      **outreach_data,
      "timestamp": datetime.utcnow().isoformat()
    })
    self._long_term[key] = existing

  def get_outreach_history(self, email: str) -> List[Dict]:
    """Get all outreach attempts for a contact"""
    key = f"outreach:{email}"
    return self._long_term.get(key, {}).get("history", [])

  # ── Vector Memory (semantic search) ───────────────────────────────────────

  def _get_chroma(self):
    """Lazy-initialize ChromaDB client and collection"""
    if self._chroma_client is None:
      try:
        import chromadb
        self._chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        self._chroma_collection = self._chroma_client.get_or_create_collection(
          name="gtm_memory",
          metadata={"hnsw:space": "cosine"}
        )
        logger.info("ChromaDB initialized")
      except ImportError:
        logger.error("chromadb not installed. Run: pip install chromadb")
        raise
    return self._chroma_client, self._chroma_collection

  async def get_embedding(self, text: str) -> List[float]:
    """Get text embedding from OpenAI"""
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        f"{OPENAI_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": text}
      )
      return resp.json()["data"][0]["embedding"]

  async def add_to_vector_store(self, doc_id: str, text: str, metadata: Optional[Dict] = None) -> None:
    """Add a document to the vector store for semantic search"""
    if not OPENAI_API_KEY:
      logger.warning("OPENAI_API_KEY not set, skipping vector store")
      return
    _, collection = self._get_chroma()
    embedding = await self.get_embedding(text)
    collection.upsert(
      ids=[doc_id],
      embeddings=[embedding],
      documents=[text],
      metadatas=[metadata or {}]
    )

  async def semantic_search(self, query: str, n_results: int = 5) -> List[Dict]:
    """Search vector store for semantically similar documents"""
    if not OPENAI_API_KEY:
      return []
    try:
      _, collection = self._get_chroma()
      query_embedding = await self.get_embedding(query)
      results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
      return [
        {"id": results["ids"][0][i], "text": results["documents"][0][i], "metadata": results["metadatas"][0][i]}
        for i in range(len(results["ids"][0]))
      ]
    except Exception as e:
      logger.warning(f"Semantic search failed: {e}")
      return []

  # ── Memory summary ──────────────────────────────────────────────────────────

  def get_stats(self) -> Dict:
    """Return memory usage statistics"""
    return {
      "short_term_sessions": len(self._short_term),
      "long_term_entities": len(self._long_term),
      "companies_stored": len(self.list_entities("company")),
      "contacts_stored": len(self.list_entities("contact")),
      "outreach_logged": len(self.list_entities("outreach"))
    }

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    action = context.get("action", "recall") if context else "recall"

    if action == "store":
      entity_type = context.get("entity_type", "company")
      entity_id = context.get("entity_id", "")
      data = context.get("data", {})
      self.store(entity_type, entity_id, data)
      return {"status": "stored", "key": f"{entity_type}:{entity_id}"}

    elif action == "recall":
      entity_type = context.get("entity_type", "company")
      entity_id = context.get("entity_id", "")
      result = self.recall(entity_type, entity_id)
      return {"status": "found" if result else "not_found", "data": result}

    elif action == "search":
      query = context.get("query", task)
      results = await self.semantic_search(query)
      return {"status": "completed", "results": results}

    elif action == "add_message":
      session_id = context.get("session_id", "default")
      role = context.get("role", "user")
      content = context.get("content", "")
      self.add_message(session_id, role, content)
      return {"status": "added"}

    elif action == "get_conversation":
      session_id = context.get("session_id", "default")
      return {"messages": self.get_conversation(session_id), "status": "success"}

    elif action == "stats":
      return {"stats": self.get_stats(), "status": "success"}

    return {"status": "error", "reason": f"Unknown action: {action}"}
