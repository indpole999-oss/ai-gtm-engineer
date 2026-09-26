from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from backend.tenancy import get_workspace_db, get_current_workspace
from backend.research_service import scoped_record
from backend.outreach_service import lock_workspace
from backend.routers.outreach import response
from backend.routers.planning import plan_response
from backend.planning_models import PlanVersion
from backend.outcome_models import PipelineRecord, PipelineHistory, CRMMapping, OutcomeAction, CalendarBooking, CRMReceipt
from backend import outcome_service as service, pipeline_service

router = APIRouter()


class StageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["discovered", "qualified", "contacted", "engaged", "interested", "meeting", "opportunity", "won", "lost"]
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=3000)
    evidence_kind: Literal["research", "outbound", "inbound", "calendar", "explicit_user"] | None = None
    evidence_id: UUID | None = None
    reviewed: Literal[True]


class RemoteReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt_id: UUID
    expected_revision: int = Field(ge=1)
    reviewed: Literal[True]


@router.get("/pipeline")
async def pipeline(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db=Depends(get_workspace_db)):
    return [response(r) for r in (await db.scalars(select(PipelineRecord).order_by(PipelineRecord.created_at, PipelineRecord.id).limit(limit).offset(offset))).all()]


@router.get("/pipeline/{record_id}")
async def detail(record_id: UUID, db=Depends(get_workspace_db)):
    row = await scoped_record(db, PipelineRecord, record_id)
    history = (await db.scalars(select(PipelineHistory).where(PipelineHistory.pipeline_id == row.id).order_by(PipelineHistory.created_at, PipelineHistory.id).limit(500))).all()
    return {**response(row), "history": [response(r) for r in history]}


@router.post("/pipeline/{record_id}/stage")
async def stage(record_id: UUID, body: StageInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    row = await scoped_record(db, PipelineRecord, record_id)
    await pipeline_service.manual(db, row, ctx, body.stage, body.expected_revision, body.reason, body.evidence_kind, body.evidence_id)
    await db.commit()
    return response(row)


async def action_response(db, action):
    plan = await scoped_record(db, PlanVersion, action.plan_id)
    booking = await db.scalar(select(CalendarBooking).where(CalendarBooking.action_id == action.id))
    result = {**response(action), "plan": plan_response(plan)}
    if booking:
        result["meeting"] = {**response(booking), "status": "scheduled" if action.state == "confirmed" else action.state,
            "provider_event_id": action.external_id, "idempotency_key": str(action.id)}
    return result


@router.post("/crm/sync", status_code=201)
async def sync(body: service.CRMInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    return await action_response(db, await service.create_action(db, ctx, body, "crm_sync"))


@router.post("/calendar/schedule", status_code=201)
async def schedule(body: service.ScheduleInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    return await action_response(db, await service.create_action(db, ctx, body, "calendar_schedule"))


@router.get("/actions")
async def actions(db=Depends(get_workspace_db)):
    return [response(r) for r in (await db.scalars(select(OutcomeAction).order_by(OutcomeAction.created_at.desc()).limit(100))).all()]


@router.get("/actions/{action_id}")
async def action(action_id: UUID, db=Depends(get_workspace_db)):
    return await action_response(db, await scoped_record(db, OutcomeAction, action_id))


@router.post("/actions/{action_id}/reconcile")
async def reconcile(action_id: UUID, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    return await action_response(db, await service.reconcile(db, await scoped_record(db, OutcomeAction, action_id), ctx))


@router.get("/crm/mappings")
async def mappings(db=Depends(get_workspace_db)):
    return [response(r) for r in (await db.scalars(select(CRMMapping).order_by(CRMMapping.created_at.desc()).limit(100))).all()]


@router.get("/crm/mappings/{mapping_id}")
async def mapping(mapping_id: UUID, db=Depends(get_workspace_db)):
    row = await scoped_record(db, CRMMapping, mapping_id)
    receipts = (await db.scalars(select(CRMReceipt).where(CRMReceipt.mapping_id == row.id).order_by(CRMReceipt.created_at.desc()).limit(100))).all()
    return {**response(row), "remote_events": [response(r) for r in receipts]}


@router.post("/crm/mappings/{mapping_id}/review-remote")
async def review(mapping_id: UUID, body: RemoteReview, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    return response(await service.review_remote(db, await scoped_record(db, CRMMapping, mapping_id), await scoped_record(db, CRMReceipt, body.receipt_id), ctx, body.expected_revision))


@router.post("/crm/simulated-events/{integration_id}", status_code=202)
async def simulated(integration_id: UUID, body: service.CRMEvent, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    integration = await service.healthy(db, integration_id, "crm_sync")
    from backend import outcome_providers
    from backend.security import decrypt_credentials
    adapter = outcome_providers.adapter_for(integration, decrypt_credentials(integration.credentials))
    if not getattr(adapter.transport, "simulated", False):
        raise HTTPException(409, "Only injected fake providers accept simulated events; live webhooks are disabled")
    return response(await service.receive_crm_event(db, integration_id, body))


@router.get("/calendar/meetings")
async def meetings(db=Depends(get_workspace_db)):
    rows = (await db.scalars(select(OutcomeAction).where(OutcomeAction.kind == "calendar_schedule").order_by(OutcomeAction.created_at.desc()).limit(100))).all()
    return [await action_response(db, row) for row in rows]


@router.get("/integration-health/{integration_id}")
async def health(integration_id: UUID, db=Depends(get_workspace_db)):
    from backend.database import Integration
    from backend.routers.integrations import integration_response
    row = await scoped_record(db, Integration, integration_id)
    return {"integration": integration_response(row), "live_outcome_writes_enabled": False}
