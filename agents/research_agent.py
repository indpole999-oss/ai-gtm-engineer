"""
Research Agent - Researches companies using Serper web search + NVIDIA NIM analysis
Steps 37-41: Company research, news, funding, tech stack, pain points
"""

import httpx
import json
import logging
from typing import Optional, Dict, Any, List
import os

logger = logging.getLogger(__name__)


NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")


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
      """Researches target companies using Serper web search + NVIDIA NIM analysis"""

    def __init__(self):
              self.serper_key = SERPER_API_KEY
              self.nvidia_key = NVIDIA_API_KEY
              self.model = NVIDIA_MODEL

    async def web_search(self, query: str, num_results: int = 5) -> List[Dict]:
              """Search the web using Serper API"""
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

          async def analyze_with_nim(self, company_name: str, search_results: List[Dict]) -> Dict:
                    """Use NVIDIA NIM to analyze and structure research data"""
                    search_text = "\n".join([
                        f"- {r.get('title')}: {r.get('snippet')}" for r in search_results[:5]
                    ])
                    messages = [
                        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Company: {company_name}\nSearch Results:\n{search_text}"}
                    ]
                    async with httpx.AsyncClient(timeout=60) as client:
                                  resp = await client.post(
                                                    f"{NVIDIA_BASE_URL}/chat/completions",
                                                    headers={"Authorization": f"Bearer {self.nvidia_key}", "Content-Type": "application/json"},
                                                    json={"model": self.model, "messages": messages, "temperature": 0.1, "max_tokens": 1500, "stream": False}
                                                )
                                  data = resp.json()
                                  content = data["choices"][0]["message"]["content"]
                                  try:
                                                    return json.loads(content)
                                                except:
                return {"raw_analysis": content}

    async def research(self, company_name: str, domain: Optional[str] = None) -> Dict[str, Any]:
              """Main research method - searches and analyzes a company"""
              logger.info(f"Researching company: {company_name}")
              queries = [
                  f"{company_name} company overview funding 2024",
                  f"{company_name} tech stack technology",
                  f"{company_name} news recent
              ]
              all_results = []
              for query in queries:
                  try:
                      results = await self.web_search(query)
                      all_results.extend(results)
                  except Exception as e:
                      logger.warning(f"Search failed for '{query}': {e}")
              analysis = await self.analyze_with_nim(company_name, all_results)
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
                  company = task.replace("Research ", "").replace("research ", "")
              return await self.research(company_name=company, domain=domain)
