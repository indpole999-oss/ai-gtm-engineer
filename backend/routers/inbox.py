from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from backend.tenancy import get_workspace_db, get_current_workspace
from backend.research_service import scoped_record
from backend.outreach_service import lock_workspace
from backend.outreach_models import SenderIdentity, Message, MessageDraft, Suppression
from backend.inbox_models import InboxThread, InboundMessage, InboxThreadLink, ReplyClassification, InboxPause, SuggestedReplyDraft
from backend.inbox_classifier import Category
from backend import inbox_service as service
from backend.planning_models import DomainEvent, OutboxEvent
from backend.routers.outreach import response

router = APIRouter()


class OverrideInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category
    reason: str = Field(min_length=10, max_length=3000)
    expected_number: int = Field(ge=0)
    reviewed: Literal[True]


async def message_response(db, message):
    classifications = (await db.scalars(select(ReplyClassification).where(ReplyClassification.inbound_message_id == message.id).order_by(ReplyClassification.number))).all()
    drafts = (await db.scalars(select(SuggestedReplyDraft).where(SuggestedReplyDraft.inbound_message_id == message.id).order_by(SuggestedReplyDraft.created_at))).all()
    pauses = (await db.scalars(select(InboxPause).where(InboxPause.inbound_message_id == message.id))).all()
    suppressed = await db.scalar(select(Suppression.id).where(Suppression.email == message.sender_email)) is not None
    return {**response(message), "classification": response(classifications[-1]) if classifications else None,
        "classification_history": [response(c) for c in classifications],
        "suggested_replies": [{**response(d), "status": "draft"} for d in drafts],
        "sequence_holds": [response(p) for p in pauses], "suppressed": suppressed,
        "processing": await service.processing_state(db, message)}


@router.post("/simulated-events/{sender_id}", status_code=202)
async def simulated_event(sender_id: UUID, body: service.InboundEvent, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    sender = await scoped_record(db, SenderIdentity, sender_id)
    if sender.provider != "fake":
        raise HTTPException(409, "Simulation requires an explicitly fake mailbox; live webhook ingestion is disabled")
    return await message_response(db, await service.ingest(db, sender.id, body))


@router.get("/threads")
async def threads(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db=Depends(get_workspace_db)):
    latest = select(func.max(InboundMessage.received_at)).where(InboundMessage.thread_id == InboxThread.id).correlate(InboxThread).scalar_subquery()
    rows = (await db.scalars(select(InboxThread).order_by(latest.desc(), InboxThread.id).limit(limit).offset(offset))).all()
    return [response(row) for row in rows]


@router.get("/threads/{thread_id}")
async def thread(thread_id: UUID, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0), db=Depends(get_workspace_db)):
    row = await scoped_record(db, InboxThread, thread_id)
    messages = (await db.scalars(select(InboundMessage).where(InboundMessage.thread_id == row.id).order_by(InboundMessage.received_at, InboundMessage.id).limit(limit).offset(offset))).all()
    links = (await db.scalars(select(InboxThreadLink).where(InboxThreadLink.thread_id == row.id).limit(100))).all()
    outbound = []
    for link in links:
        sent = await scoped_record(db, Message, link.outbound_message_id)
        draft = await scoped_record(db, MessageDraft, sent.draft_id)
        outbound.append({"id": sent.id, "state": sent.state, "provider_message_id": sent.provider_message_id, "accepted_at": sent.accepted_at, "envelope": draft.envelope})
    return {**response(row), "messages": [await message_response(db, m) for m in messages], "outbound_messages": outbound}


@router.get("/messages/{message_id}")
async def message(message_id: UUID, db=Depends(get_workspace_db)):
    return await message_response(db, await scoped_record(db, InboundMessage, message_id))


@router.post("/messages/{message_id}/override", status_code=201)
async def override(message_id: UUID, body: OverrideInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    row = await scoped_record(db, InboundMessage, message_id)
    return response(await service.override(db, row, ctx, body.category, body.reason, body.expected_number))


@router.post("/messages/{message_id}/suggested-reply", status_code=201)
async def suggest(message_id: UUID, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    row = await service.suggest(db, await scoped_record(db, InboundMessage, message_id), ctx)
    return {**response(row), "status": "draft"}


@router.get("/drafts/{draft_id}")
async def draft(draft_id: UUID, db=Depends(get_workspace_db)):
    return {**response(await scoped_record(db, SuggestedReplyDraft, draft_id)), "status": "draft"}


@router.post("/messages/{message_id}/retry-classification")
async def retry(message_id: UUID, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    row = await scoped_record(db, InboundMessage, message_id)
    event = await db.scalar(select(DomainEvent).where(DomainEvent.kind == "inbound_received", DomainEvent.data["inbound_message_id"].as_string() == str(row.id)))
    work = await db.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event.id).with_for_update()) if event else None
    if not work or work.status != "failed":
        raise HTTPException(409, "Only failed classification can be retried")
    work.status, work.attempts, work.due_at = "pending", 0, datetime.utcnow()
    work.lease_token, work.lease_until, work.error_code = None, None, None
    await service.audit(db, row, "inbound_retry_requested", {"actor": str(ctx.user_id)})
    await db.commit()
    return await service.processing_state(db, row)
