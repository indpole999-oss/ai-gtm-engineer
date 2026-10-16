from backend.tenancy import require_approved_execution
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from backend.routers.auth import get_current_user
from workflows.workflow_engine import WorkflowEngine


router = APIRouter()


WORKFLOWS = {
    "lead_pipeline": "Lead pipeline automation",
    "email_sequence": "Email outreach automation",
}


class WorkflowRequest(BaseModel):
    workflow_name: str
    context: Dict[str, Any] = {}


@router.get("/")
async def list_workflows(
    current_user=Depends(get_current_user),
):
    return {
        "status": "success",
        "workflows": WORKFLOWS,
    }


@router.get("/{workflow_name}")
async def get_workflow(
    workflow_name: str,
    current_user=Depends(get_current_user),
):
    if workflow_name not in WORKFLOWS:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    return {
        "status": "success",
        "name": workflow_name,
        "description": WORKFLOWS[workflow_name],
    }


@router.post("/run", dependencies=[Depends(require_approved_execution)])
async def run_workflow(
    request: WorkflowRequest,
    current_user=Depends(get_current_user),
):
    if request.workflow_name not in WORKFLOWS:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    context = dict(request.context)

    # Pass the authenticated user to agents that need
    # user-specific integrations such as Google Calendar.
    context["user_id"] = str(current_user.id)

    engine = WorkflowEngine()

    result = await engine.execute(
        workflow_name=request.workflow_name,
        context=context,
    )

    return result