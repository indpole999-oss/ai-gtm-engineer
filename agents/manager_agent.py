"""
Manager Agent - Orchestrates all GTM sub-agents via NVIDIA NIM
Steps 17-25: Task routing, agent coordination, decision making
"""

import httpx
import json
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)


NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")


AGENT_ROUTING_PROMPT = """
You are the Manager Agent for an AI GTM (Go-To-Market) Engineer system.
Your job is to analyze incoming tasks and route them to the correct specialist agent.

Available agents:
- research: Researches companies, industries, news, funding, tech stack using web search
- enrichment: Enriches lead/contact data with emails, phones, titles from Apollo.io
- email: Writes personalized cold outreach emails based on research and context
- crm: Updates HubSpot CRM with deal stages, notes, contacts, activities
- calendar: Books discovery call meetings via Google Calendar
- manager: Handles complex multi-step tasks requiring coordination of multiple agents

Given the task description, respond with ONLY a JSON object:
{"agent": "agent_name", "reasoning": "why this agent", "subtasks": []}
"""


class ManagerAgent:
      """Orchestrator agent that routes tasks to specialist agents using NVIDIA NIM"""

    def __init__(self):
              self.model = NVIDIA_MODEL
              self.api_key = NVIDIA_API_KEY
              self.base_url = NVIDIA_BASE_URL

    async def call_nvidia_nim(self, messages: list, temperature: float = 0.2) -> str:
              """Call NVIDIA NIM API for LLM inference"""
              headers = {
                  "Authorization": f"Bearer {self.api_key}",
                  "Content-Type": "application/json"
              }
              payload = {
                  "model": self.model,
                  "messages": messages,
                  "temperature": temperature,
                  "max_tokens": 1024,
                  "stream": False
              }
              async with httpx.AsyncClient(timeout=60) as client:
                            response = await client.post(
                                              f"{self.base_url}/chat/completions",
                                              headers=headers,
                                              json=payload
                                          )
                            response.raise_for_status()
                            data = response.json()
                            return data["choices"][0]["message"]["content"]

          async def route_task(self, task: str) -> Dict[str, Any]:
                    """Determine which agent should handle the task"""
                    messages = [
                        {"role": "system", "content": AGENT_ROUTING_PROMPT},
                        {"role": "user", "content": f"Task: {task}"}
                    ]
                    try:
                                  response = await self.call_nvidia_nim(messages)
                                  return json.loads(response)
                              except Exception as e:
                                            logger.error(f"Routing failed: {e}")
                                            return {"agent": "research", "reasoning": "Default fallback", "subtasks": []}

                async def run(self, task: str, target_agent: Optional[str] = None, context: Optional[Dict] = None) -> Dict[str, Any]:
                          """Main entry point - route and execute task"""
                          logger.info(f"Manager Agent received task: {task}")

        # Determine routing
        if target_agent:
                      routing = {"agent": target_agent, "reasoning": "Explicitly specified", "subtasks": []}
                  else:
            routing = await self.route_task(task)

                            agent_name = routing.get("agent", "research")
        logger.info(f"Routing to {agent_name} agent: {routing.get('reasoning')}")

        # Execute with correct agent
        if agent_name == "research":
                      from agents.research_agent import ResearchAgent
                      agent = ResearchAgent()
                      result = await agent.run(task=task, context=context or {})
                  elif agent_name == "enrichment":
                                from agents.enrichment_agent import EnrichmentAgent
                                agent = EnrichmentAgent()
                                result = await agent.run(task=task, context=context or {})
                            elif agent_name == "email":
                                          from agents.email_agent import EmailAgent
                                          agent = EmailAgent()
                                          result = await agent.run(task=task, context=context or {})
                                      else:
            result = {"message": f"Agent '{agent_name}' received task", "task": task, "status": "acknowledged"}

        return {
                      "agent_used": agent_name,
                      "routing_reasoning": routing.get("reasoning"),
                      "result": result,
                      "task": task
                  }
