from typing import Literal
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from backend.database import Integration, Meeting, CRMRecord
from backend.planning_models import Goal, PlanVersion, ExecutionCycle, StepRun, ActionCommand, DomainEvent
from backend import planning_service as service
from backend.execution_worker import approved
from backend.research_service import scoped_record
from backend.tenancy import get_current_workspace, get_workspace_db

router = APIRouter()


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=10, max_length=4000)
    brain_version_id: UUID
    targets: list[service.Target] = Field(min_length=1, max_length=20)


class GenerateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["local_ai", "research_template"]


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_hash: str = Field(pattern="^[0-9a-f]{64}$")
    reviewed: Literal[True]


class ControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["pause", "resume", "cancel"]


def plan_response(row):
    return {"id": row.id, "goal_id": row.goal_id, "number": row.number, "status": row.status,
            "document": row.document, "content_hash": row.content_hash, "author_method": row.author_method,
            "approved_at": row.approved_at}


@router.post("/goals", status_code=201)
async def create_goal(body: GoalInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    targets = [t.model_dump(mode="json") for t in body.targets]
    await service.validate_targets(db, body.brain_version_id, targets)
    row = Goal(objective=body.objective, brain_version_id=body.brain_version_id, created_by=ctx.user_id, target_inputs=targets)
    db.add(row)
    await db.commit()
    return {"id": row.id, "objective": row.objective}


@router.get("/goals")
async def goals(db=Depends(get_workspace_db)):
    rows = (await db.scalars(select(Goal).order_by(Goal.created_at.desc()).limit(100))).all()
    return [{"id": row.id, "objective": row.objective, "brain_version_id": row.brain_version_id} for row in rows]


@router.post("/goals/{goal_id}/plans", status_code=201)
async def generate(goal_id: UUID, body: GenerateInput, db=Depends(get_workspace_db)):
    goal = await db.scalar(select(Goal).where(Goal.id == goal_id).with_for_update())
    if not goal:
        raise HTTPException(404, "Goal not found")
    brain = await service.validate_targets(db, goal.brain_version_id, goal.target_inputs)
    if body.mode == "research_template":
        document, method = service.research_template(goal, brain), "explicit_research_template"
    else:
        integrations = (await db.scalars(select(Integration))).all()
        context = {"objective": goal.objective, "company_brain": brain.profile, "brain_hash": brain.content_hash,
                   "targets": goal.target_inputs,
                   "integrations": [{"category": i.category, "provider": i.provider, "health": i.health} for i in integrations],
                   "workspace_policy": {"approval_required": True, "paid_budget_cents": 0, "max_steps": 20, "allowed_actions": ["research"]},
                   "historical_outcomes": {"completed_cycles": await db.scalar(select(func.count(ExecutionCycle.id)).where(ExecutionCycle.status == "completed")), "meetings": await db.scalar(select(func.count(Meeting.id)))},
                   "pipeline_state": {"crm_records": await db.scalar(select(func.count(CRMRecord.id)))}}
        try:
            document, method = await service.planner_provider().plan(context)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(503, "The local planner could not produce a valid plan. No execution was started.") from None
    return plan_response(await service.save_plan(db, goal, document, method))


@router.get("/goals/{goal_id}/plans")
async def plans(goal_id: UUID, db=Depends(get_workspace_db)):
    await scoped_record(db, Goal, goal_id)
    rows = (await db.scalars(select(PlanVersion).where(PlanVersion.goal_id == goal_id).order_by(PlanVersion.number.desc()))).all()
    return [plan_response(row) for row in rows]


@router.get("/plans/{plan_id}")
async def plan(plan_id: UUID, db=Depends(get_workspace_db)):
    return plan_response(await scoped_record(db, PlanVersion, plan_id))


@router.post("/plans/{plan_id}/revisions", status_code=201)
async def revise(plan_id: UUID, body: service.PlanDocument, db=Depends(get_workspace_db)):
    previous = await scoped_record(db, PlanVersion, plan_id)
    goal = await db.scalar(select(Goal).where(Goal.id == previous.goal_id).with_for_update())
    return plan_response(await service.save_plan(db, goal, body, "customer_revision"))


@router.post("/plans/{plan_id}/approve", status_code=201)
async def approve(plan_id: UUID, body: ApprovalInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    row = await db.scalar(select(PlanVersion).where(PlanVersion.id == plan_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Plan not found")
    cycle = await service.approve_plan(db, row, ctx, body.content_hash)
    return {"id": cycle.id, "status": cycle.status}


@router.get("/cycles")
async def cycles(db=Depends(get_workspace_db)):
    rows = (await db.scalars(select(ExecutionCycle).order_by(ExecutionCycle.created_at.desc()).limit(100))).all()
    return [{"id": row.id, "plan_id": row.plan_id, "status": row.status, "stop_reason": row.stop_reason} for row in rows]


@router.get("/cycles/{cycle_id}")
async def cycle(cycle_id: UUID, db=Depends(get_workspace_db)):
    row = await scoped_record(db, ExecutionCycle, cycle_id)
    steps = (await db.scalars(select(StepRun).where(StepRun.cycle_id == row.id).order_by(StepRun.position))).all()
    commands = (await db.scalars(select(ActionCommand).where(ActionCommand.cycle_id == row.id))).all()
    events = (await db.scalars(select(DomainEvent).where(DomainEvent.cycle_id == row.id).order_by(DomainEvent.created_at))).all()
    return {"id": row.id, "status": row.status, "stop_reason": row.stop_reason,
            "steps": [{"position": s.position, "status": s.status, "output": s.output} for s in steps],
            "commands": [{"id": c.id, "status": c.status, "attempts": c.attempts, "error_code": c.error_code} for c in commands],
            "events": [{"kind": e.kind, "at": e.created_at, "data": e.data} for e in events]}


@router.post("/cycles/{cycle_id}/control")
async def control(cycle_id: UUID, body: ControlInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    row = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == cycle_id).with_for_update())
    if not row:
        raise HTTPException(404, "Cycle not found")
    if row.status in {"completed", "cancelled", "failed"}:
        raise HTTPException(409, "Cycle is terminal; create and review a new plan version")
    if body.action == "resume":
        if not await approved(db, row):
            raise HTTPException(409, "Approval is no longer valid")
        pending = await db.scalar(select(StepRun.id).where(StepRun.cycle_id == row.id, StepRun.status != "succeeded").limit(1))
        row.status = "running" if pending else "completed"
    elif body.action == "pause":
        row.status = "paused"
    else:
        row.status = "cancelled"
        for command in (await db.scalars(select(ActionCommand).where(ActionCommand.cycle_id == row.id, ActionCommand.status.in_(["queued", "running"])))).all():
            command.status, command.lease_token, command.lease_until = "cancelled", None, None
        for step in (await db.scalars(select(StepRun).where(StepRun.cycle_id == row.id, StepRun.status.in_(["pending", "running"])))).all():
            step.status = "cancelled"
    await service.emit(db, row, "cycle_" + body.action, {"actor": str(ctx.user_id)})
    await db.commit()
    return {"id": row.id, "status": row.status}
