from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy import select
from backend.database import Contact, Integration
from backend.tenancy import get_current_workspace, get_workspace_db
from backend.research_service import scoped_record
from backend.research_models import ResearchJob
from backend.outreach_models import Campaign, Sequence, SequenceVersion, SequenceStep, SenderIdentity, Enrollment, ScheduledMessage, MessageDraft, Message, Suppression, DeliveryEvent
from backend import outreach_service as service
from backend.planning_models import PlanVersion, ActionCommand, ExecutionCycle, StepRun
from backend.planning_service import digest, emit
from backend.routers.planning import ApprovalInput, plan_response

router = APIRouter()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Named(Input):
    name: str = Field(min_length=1, max_length=200)


class SequenceInput(Named):
    campaign_id: UUID


class StepInput(Input):
    delay_seconds: int = Field(ge=0, le=2592000)
    purpose: str = Field(min_length=1, max_length=2000)


class VersionInput(Input):
    steps: list[StepInput] = Field(min_length=1, max_length=10)


class SenderInput(Input):
    email: EmailStr
    provider: Literal["fake", "gmail", "outlook"]
    integration_id: UUID | None = None
    daily_limit: int = Field(default=20, ge=1, le=100)


class EnrollmentInput(Input):
    version_id: UUID
    contact_id: UUID
    sender_id: UUID
    research_job_id: UUID


class SuppressionInput(Input):
    email: EmailStr
    reason: Literal["unsubscribe", "suppressed", "bounce", "complaint"]


class ControlInput(Input):
    status: Literal["active", "paused", "cancelled"]


def response(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


RESOURCES = {"campaigns": Campaign, "sequences": Sequence, "versions": SequenceVersion, "steps": SequenceStep,
    "senders": SenderIdentity, "enrollments": Enrollment, "scheduled": ScheduledMessage, "drafts": MessageDraft,
    "messages": Message, "suppressions": Suppression, "delivery-events": DeliveryEvent}


@router.get("/{resource}")
async def listing(resource: str, db=Depends(get_workspace_db)):
    model = RESOURCES.get(resource)
    if not model:
        raise HTTPException(404, "Resource not found")
    return [response(row) for row in (await db.scalars(select(model).order_by(model.created_at.desc()).limit(100))).all()]


@router.get("/{resource}/{record_id}")
async def detail(resource: str, record_id: UUID, db=Depends(get_workspace_db)):
    model = RESOURCES.get(resource)
    if not model:
        raise HTTPException(404, "Resource not found")
    return response(await scoped_record(db, model, record_id))


@router.post("/campaigns", status_code=201)
async def campaign(body: Named, db=Depends(get_workspace_db)):
    row = Campaign(name=body.name)
    db.add(row)
    await db.commit()
    return response(row)


@router.post("/sequences", status_code=201)
async def sequence(body: SequenceInput, db=Depends(get_workspace_db)):
    await scoped_record(db, Campaign, body.campaign_id)
    row = Sequence(**body.model_dump())
    db.add(row)
    await db.commit()
    return response(row)


@router.post("/sequences/{sequence_id}/versions", status_code=201)
async def version(sequence_id: UUID, body: VersionInput, db=Depends(get_workspace_db)):
    await service.lock_workspace(db)
    await scoped_record(db, Sequence, sequence_id)
    previous = await db.scalar(select(SequenceVersion).where(SequenceVersion.sequence_id == sequence_id).order_by(SequenceVersion.number.desc()).limit(1))
    definition = body.model_dump(mode="json")
    row = SequenceVersion(sequence_id=sequence_id, number=previous.number + 1 if previous else 1, definition=definition, content_hash=digest(definition))
    db.add(row)
    await db.flush()
    for i, step in enumerate(body.steps):
        db.add(SequenceStep(version_id=row.id, position=i, **step.model_dump()))
    await db.commit()
    return response(row)


@router.post("/senders", status_code=201)
async def sender(body: SenderInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    if body.provider != "fake":
        if not body.integration_id:
            raise HTTPException(422, "Workspace sender integration is required")
        integration = await scoped_record(db, Integration, body.integration_id)
        if integration.provider != body.provider or integration.category != "email":
            raise HTTPException(409, "Sender integration mismatch")
    row = SenderIdentity(**{**body.model_dump(), "email": service.address(body.email)}, status="connected" if body.provider == "fake" else "disabled")
    db.add(row)
    await db.commit()
    return response(row)


@router.post("/enrollments", status_code=201)
async def enroll(body: EnrollmentInput, db=Depends(get_workspace_db)):
    await service.lock_workspace(db)
    version = await scoped_record(db, SequenceVersion, body.version_id)
    contact = await scoped_record(db, Contact, body.contact_id)
    await scoped_record(db, SenderIdentity, body.sender_id)
    job = await scoped_record(db, ResearchJob, body.research_job_id)
    if job.company_id != contact.company_id or job.status != "completed":
        raise HTTPException(409, "Completed research for this contact required")
    await service.unsuppressed(db, contact.email)
    existing = await db.scalar(select(Enrollment).where(Enrollment.version_id == body.version_id, Enrollment.contact_id == body.contact_id))
    if existing:
        if existing.sender_id != body.sender_id or existing.research_job_id != body.research_job_id:
            raise HTTPException(409, "Enrollment inputs conflict")
        return response(existing)
    row = Enrollment(**body.model_dump())
    db.add(row)
    await db.flush()
    due = datetime.utcnow()
    steps = (await db.scalars(select(SequenceStep).where(SequenceStep.version_id == version.id).order_by(SequenceStep.position))).all()
    for step in steps:
        due += timedelta(seconds=step.delay_seconds)
        db.add(ScheduledMessage(enrollment_id=row.id, sequence_step_id=step.id, due_at=due))
    await db.commit()
    return response(row)


@router.post("/{resource}/{record_id}/control")
async def control(resource: Literal["campaigns", "enrollments"], record_id: UUID, body: ControlInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    await service.lock_workspace(db)
    row = await scoped_record(db, RESOURCES[resource], record_id)
    if row.status == "cancelled":
        raise HTTPException(409, "Cancelled outreach cannot resume")
    row.status = body.status
    await db.commit()
    return response(row)


@router.post("/scheduled/{scheduled_id}/drafts", status_code=201)
async def compose(scheduled_id: UUID, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    return response(await service.compose(db, await scoped_record(db, ScheduledMessage, scheduled_id), ctx.user_id))


@router.post("/drafts/{draft_id}/approve", status_code=201)
async def approve(draft_id: UUID, body: ApprovalInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    message = await service.approve_message(db, await scoped_record(db, MessageDraft, draft_id), ctx, body.content_hash)
    return {"message": response(message), "plan": plan_response(await scoped_record(db, PlanVersion, message.plan_id))}


@router.post("/suppressions", status_code=201)
async def suppress(body: SuppressionInput, db=Depends(get_workspace_db)):
    await service.lock_workspace(db)
    email = service.address(body.email)
    row = await db.scalar(select(Suppression).where(Suppression.email == email))
    if not row:
        row = Suppression(email=email, reason=body.reason)
        db.add(row)
    await db.commit()
    return response(row)


@router.post("/messages/{message_id}/retry")
async def retry(message_id: UUID, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    await service.lock_workspace(db)
    message = await scoped_record(db, Message, message_id)
    await service.valid_message(db, message, message.plan_id)
    cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.plan_id == message.plan_id).with_for_update())
    from backend.execution_worker import approved
    if not cycle or cycle.status != "failed" or not await approved(db, cycle):
        raise HTTPException(409, "Only failed, still-approved execution can be retried")
    command = await db.scalar(select(ActionCommand).where(ActionCommand.cycle_id == cycle.id))
    step = await scoped_record(db, StepRun, command.step_id)
    command.status, command.attempts, command.due_at = "queued", 0, datetime.utcnow()
    command.lease_token, command.lease_until = None, None
    step.status, cycle.status, cycle.stop_reason = "pending", "running", None
    await emit(db, cycle, "outreach_retry_requested", {"message_id": str(message.id), "actor": str(ctx.user_id)})
    await db.commit()
    return response(message)
