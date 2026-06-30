"""
Agents Router - API endpoints to invoke AI GTM agents
Steps 17-25: Manager, Research, Enrichment, Email, CRM, Calendar agents
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx

from backend.routers.auth import get_current_user
from backend.config import settings

router = APIRouter()


class AgentTask(BaseModel):
      agent: str  # manager, research, enrichment, email, crm, calendar
    task: str
    context: Optional[Dict[str, Any]] = {}


AGENT_DESCRIPTIONS = {
      "manager": "Orchestrates all agents and routes tasks",
      "research": "Researches companies using Serper web search",
      "enrichment": "Enriches lead data using Apollo.io",
      "email": "Personalizes and sends outreach emails",
      "crm": "Updates HubSpot CRM with deal data",
      "calendar": "Books meetings via Google Calendar",
  }


@router.get("/")
async def list_agents(current_user=Depends(get_current_user)):
      """List all available GTM agents and their capabilities"""
      return {"agents": AGENT_DESCRIPTIONS, "total": len(AGENT_DESCRIPTIONS)}


@router.post("/run")
async def run_agent(
      task: AgentTask,
      background_tasks: BackgroundTasks,
      current_user=Depends(get_current_user)
  ):
        """Dispatch task to the Manager Agent which routes to correct sub-agent"""
        if task.agent not in AGENT_DESCRIPTIONS:
                  raise HTTPException(status_code=400, detail=f"Unknown agent: {task.agent}")
              # Import and run the manager agent
              from agents.manager_agent import ManagerAgent
    agent = ManagerAgent()
    result = await agent.run(task=task.task, target_agent=task.agent, context=task.context)
    return {"agent": task.agent, "task": task.task, "result": result, "status": "completed"}


@router.post("/research")
async def research_company(company_name: str, domain: Optional[str] = None, current_user=Depends(get_current_user)):
      """Trigger Research Agent for a specific company"""
    from agents.research_agent import ResearchAgent
    agent = ResearchAgent()
    result = await agent.research(company_name=company_name, domain=domain)
    return {"company": company_name, "research": result, "status": "completed"}
