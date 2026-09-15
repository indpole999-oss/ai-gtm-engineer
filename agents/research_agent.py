"""
Research Agent - Web search + Ollama local LLM
Uses Tavily/Serper for research and Ollama for analysis
"""

import httpx
import json
import logging
import os

from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


# Search APIs
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


# Ollama Local LLM
OLLAMA_BASE_URL = "http://localhost:11434/api"
OLLAMA_MODEL = "qwen3:4b"


RESEARCH_SYSTEM_PROMPT = """
You are a GTM Research Agent.

Analyze company information and extract:

1. Company overview
2. Recent news and funding
3. Technology stack
4. Business pain points
5. Decision makers and buying signals
6. Opportunity score from 1-10

Return ONLY valid JSON.

Format:

{
 "overview":"",
 "recent_news":"",
 "tech_stack":[],
 "pain_points":[],
 "decision_makers":[],
 "opportunity_score":0
}
"""


class ResearchAgent:

    def __init__(self):

        self.serper_key = SERPER_API_KEY
        self.tavily_key = TAVILY_API_KEY

        self.ollama_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL


    async def web_search_serper(
            self,
            query: str,
            num_results: int = 5
    ) -> List[Dict]:


        if not self.serper_key:
            return []


        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "num": num_results
                }
            )

            response.raise_for_status()

            data = response.json()

            return data.get("organic", [])



    async def web_search_tavily(
            self,
            query: str,
            num_results: int = 5
    ) -> List[Dict]:


        if not self.tavily_key:
            return []


        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": query,
                    "max_results": num_results,
                    "search_depth": "basic"
                }
            )


            response.raise_for_status()

            data = response.json()


            return [
                {
                    "title": r.get("title"),
                    "snippet": r.get("content"),
                    "link": r.get("url")
                }
                for r in data.get("results", [])
            ]



    async def web_search(
            self,
            query: str,
            num_results: int = 5
    ):


        if self.serper_key:

            return await self.web_search_serper(
                query,
                num_results
            )


        if self.tavily_key:

            return await self.web_search_tavily(
                query,
                num_results
            )


        logger.warning(
            "No search API configured"
        )

        return []



    async def analyze_with_llm(
            self,
            company_name: str,
            search_results: List[Dict]
    ) -> Dict:


        if not search_results:

            return {
                "error": "No research data found"
            }


        search_text = "\n".join(
            [
                f"- {r.get('title','')}: {r.get('snippet','')[:300]}"
                for r in search_results[:5]
            ]
        )


        prompt = f"""
{RESEARCH_SYSTEM_PROMPT}

Company:
{company_name}

Research Data:
{search_text}

Return ONLY JSON.
"""


        try:

            async with httpx.AsyncClient(timeout=300) as client:

                response = await client.post(
                    f"{self.ollama_url}/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0,
                            "num_predict": 400
                        }
                    }
                )


                response.raise_for_status()

                data = response.json()


                content = data.get(
                    "response",
                    ""
                ).strip()



                if content.startswith("```json"):

                    content = content.replace(
                        "```json",
                        ""
                    )


                if content.startswith("```"):

                    content = content.replace(
                        "```",
                        ""
                    )


                if content.endswith("```"):

                    content = content[:-3]


                content = content.strip()


                try:

                    return json.loads(content)


                except Exception:

                    return {
                        "raw_analysis": content
                    }



        except Exception as e:


            logger.error(
                f"Ollama Error: {e}"
            )


            return {
                "error": str(e)
            }



    async def research(
            self,
            company_name: str,
            domain: Optional[str] = None
    ) -> Dict[str, Any]:


        logger.info(
            f"Researching {company_name}"
        )


        queries = [

            f"{company_name} company overview",

            f"{company_name} funding news",

            f"{company_name} technology stack",

            f"{company_name} challenges pain points"

        ]


        all_results = []


        for query in queries:

            try:

                results = await self.web_search(query)

                all_results.extend(results)


            except Exception as e:

                logger.warning(
                    f"Search failed: {e}"
                )



        analysis = await self.analyze_with_llm(
            company_name,
            all_results
        )



        return {

            "company": company_name,

            "domain": domain,

            "sources_found": len(all_results),

            "analysis": analysis,

            "status": "completed"

        }



    async def run(
            self,
            task: str,
            context: Optional[Dict] = None
    ) -> Dict[str, Any]:


        company = None


        if context:

            company = context.get('company_name') or context.get('company')


        if not company:

            company = (
                task
                .replace("Research ", "")
                .replace("research ", "")
                .strip()
            )


        return await self.research(company, context.get('domain') if context else None)


