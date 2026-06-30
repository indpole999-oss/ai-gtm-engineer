"""
Research Agent - Web search only (Serper/Tavily)
Steps 37-41: Company research, news, funding, tech stack, pain points
No NVIDIA NIM dependency - uses OpenAI-compatible LLM for analysis
"""
import httpx
import json
import logging
from typing import Optional, Dict, Any, List
import os

logger = logging.getLogger(__name__)

# --- API Keys ---
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

RESEARCH_SYSTEM_PROMPT = """
You are a GTM Research Agent. Your job is to analyze company information and extract:
1. Company overview (what they do, size, stage)
2. Recent news and funding
3. Technology stack they use
4. Key pain points and challenges
5. Decision makers and buying signals
Format your response as JSON with keys: overview, recent_news, tech_stack, pain_points, decision_makers, opportunity_score (1-10)
"""


class ResearchAgent:
  """Researches target companies using Serper/Tavily web search + LLM analysis"""

  def __init__(self):
    self.serper_key = SERPER_API_KEY
    self.tavily_key = TAVILY_API_KEY
    self.openai_key = OPENAI_API_KEY
    self.model = OPENAI_MODEL

  async def web_search_serper(self, query: str, num_results: int = 5) -> List[Dict]:
    """Search the web using Serper API"""
    if not self.serper_key:
      logger.warning("SERPER_API_KEY not set, skipping Serper search")
      return []
    async with httpx.AsyncClient(timeout=30) as client:
      response = await client.post(
        "https://google.serper.dev/search",
        headers={
          "X-API-KEY": self.serper_key,
          "Content-Type": "application/json"
        },
        json={"q": query, "num": num_results}
      )
      data = response.json()
      return data.get("organic", [])

  async def web_search_tavily(self, query: str, num_results: int = 5) -> List[Dict]:
    """Search the web using Tavily API as fallback"""
    if not self.tavily_key:
      logger.warning("TAVILY_API_KEY not set, skipping Tavily search")
      return []
    async with httpx.AsyncClient(timeout=30) as client:
      response = await client.post(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        json={
          "api_key": self.tavily_key,
          "query": query,
          "max_results": num_results,
          "search_depth": "basic"
        }
      )
      data = response.json()
      results = data.get("results", [])
      # Normalize to Serper-like format
      return [
        {"title": r.get("title"), "snippet": r.get("content"), "link": r.get("url")}
        for r in results
      ]

  async def web_search(self, query: str, num_results: int = 5) -> List[Dict]:
    """Search using Serper first, fall back to Tavily"""
    if self.serper_key:
      return await self.web_search_serper(query, num_results)
    elif self.tavily_key:
      return await self.web_search_tavily(query, num_results)
    else:
      logger.error("No search API key configured (SERPER_API_KEY or TAVILY_API_KEY)")
      return []

  async def analyze_with_llm(self, company_name: str, search_results: List[Dict]) -> Dict:
    """Use OpenAI-compatible LLM to analyze and structure research data"""
    if not self.openai_key:
      logger.warning("OPENAI_API_KEY not set, returning raw results")
      return {"raw_results": search_results[:5]}

    search_text = "\n".join([
      f"- {r.get('title')}: {r.get('snippet')}" for r in search_results[:10]
    ])
    messages = [
      {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
      {"role": "user", "content": f"Company: {company_name}\nSearch Results:\n{search_text}"}
    ]
    async with httpx.AsyncClient(timeout=60) as client:
      resp = await client.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
          "Authorization": f"Bearer {self.openai_key}",
          "Content-Type": "application/json"
        },
        json={
          "model": self.model,
          "messages": messages,
          "temperature": 0.1,
          "max_tokens": 1500
        }
      )
      data = resp.json()
      content = data["choices"][0]["message"]["content"]
      try:
        # Strip markdown code fences if present
        clean = content.strip()
        if clean.startswith("```"):
          clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(clean)
      except Exception:
        return {"raw_analysis": content}

  async def research(self, company_name: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Main research method - searches and analyzes a company"""
    logger.info(f"Researching company: {company_name}")

    queries = [
      f"{company_name} company overview funding 2024",
      f"{company_name} tech stack technology",
      f"{company_name} recent news announcements",
      f"{company_name} pain points challenges"
    ]

    all_results = []
    for query in queries:
      try:
        results = await self.web_search(query)
        all_results.extend(results)
      except Exception as e:
        logger.warning(f"Search failed for '{query}': {e}")

    analysis = await self.analyze_with_llm(company_name, all_results)
    return {
      "company": company_name,
      "domain": domain,
      "sources_found": len(all_results),
      "analysis": analysis,
      "status": "completed"
    }

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    company = context.get("company") if context else None
    domain = context.get("domain") if context else None
    if not company:
      company = task.replace("Research ", "").replace("research ", "").strip()
    return await self.research(company_name=company, domain=domain)
