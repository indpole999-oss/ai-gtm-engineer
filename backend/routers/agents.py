from backend.tenancy import require_approved_execution
"""
Agents Router - API endpoints to invoke AI GTM agents
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

from backend.routers.auth import get_current_user


router = APIRouter()


VALID_AGENTS = Literal[
    "manager",
    "research",
    "enrichment",
    "email",
    "crm",
    "calendar",
]


class AgentTask(BaseModel):
    agent: VALID_AGENTS = Field(
        ...,
        description="AI agent to execute the task",
        examples=["research"]
    )

    task: str = Field(
        ...,
        description="Task instruction for the agent",
        examples=["Research this company and find sales opportunities"]
    )

    context: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional task context"
    )


class AgentsListResponse(BaseModel):
    agents: Dict[str, str]
    total: int


class AgentRunResponse(BaseModel):
    agent: str
    task: str
    result: Dict[str, Any]
    status: str


AGENT_DESCRIPTIONS = {
    "manager": "Orchestrates all agents and routes tasks",
    "research": "Researches companies using Serper web search",
    "enrichment": "Enriches lead data using Apollo.io",
    "email": "Personalizes and sends outreach emails",
    "crm": "Updates HubSpot CRM with deal data",
    "calendar": "Books meetings via Google Calendar",
}


@router.get(
    "/",
    response_model=AgentsListResponse
)
async def list_agents(
    current_user=Depends(get_current_user)
):
    """
    List all available GTM agents.
    """

    return {
        "agents": AGENT_DESCRIPTIONS,
        "total": len(AGENT_DESCRIPTIONS)
    }


@router.post("/run", dependencies=[Depends(require_approved_execution)],
    response_model=AgentRunResponse,
    responses={
        400: {
            "description": "Invalid agent name"
        }
    }
)
async def run_agent(
    task: AgentTask,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """
    Dispatch task to the selected AI agent.
    """

    if task.agent not in AGENT_DESCRIPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent: {task.agent}"
        )


    from agents.manager_agent import ManagerAgent


    agent = ManagerAgent()

    result = await agent.run(
        task=task.task,
        target_agent=task.agent,
        context=task.context,
    )


    return {
        "agent": task.agent,
        "task": task.task,
        "result": result,
        "status": "completed",
    }


@router.post("/research", dependencies=[Depends(require_approved_execution)])
async def research_company(
    company_name: str,
    domain: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    Trigger Research Agent for a company.
    """

    from agents.research_agent import ResearchAgent


    agent = ResearchAgent()

    result = await agent.research(
        company_name=company_name,
        domain=domain,
    )


    return {
        "company": company_name,
        "research": result,
        "status": "completed",
    }