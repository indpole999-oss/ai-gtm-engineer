"""Trusted ingestion, deterministic association and append-only inbox decisions.

The caller must authenticate the provider before binding its workspace/mailbox.
The only HTTP ingestion exposed in Phase 7 is an administrator-only fake adapter.
"""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from backend.research_service import scoped_record
from backend.outreach_service import address, lock_workspace
from backend.outreach_models import SenderIdentity, Message, MessageDraft, Enrollment, ScheduledMessage, Suppression
from backend.planning_models import ExecutionCycle, DomainEvent, OutboxEvent
from backend.planning_service import digest, emit
from backend.inbox_models import InboxThread, InboundMessage, InboundReceipt, InboxThreadLink, ReplyClassification, InboxPause, SuggestedReplyDraft
from backend.inbox_classifier import classify, Classification, ACTIONS


class InboundEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_event_id: str = Field(min_length=1, max_length=255)
    provider_message_id: str = Field(min_length=1, max_length=255)
    provider_thread_id: str | None = Field(default=None, min_length=1, max_length=255)
    in_reply_to: str | None = Field(default=None, min_length=1, max_length=255)
    sender_email: EmailStr
    recipient_email: EmailStr
    subject: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=100000)
    auto_submitted: Literal["no", "auto-replied", "auto-generated"] = "no"
    received_at: datetime | None = None


async def message_cycle(db, message):
    if not message.outbound_message_id:
        return None
    outbound = await scoped_record(db, Message, message.outbound_message_id)
    return await db.scalar(select(ExecutionCycle).where(ExecutionCycle.plan_id == outbound.plan_id))


async def audit(db, message, kind, data=None):
    return await emit(db, await message_cycle(db, message), kind, {"inbound_message_id": str(message.id), **(data or {})})


async def inbox_hold(db, enrollment_id):
    return await db.scalar(select(InboxPause.id).where(InboxPause.enrollment_id == enrollment_id).limit(1)) is not None


async def protect_reply(db, message, category):
    # Called within the shared workspace dispatch lock. Receipt acknowledgement
    # and safety effects commit together, before deferred classification runs.
    if category == "unsubscribe":
        if not await db.scalar(select(Suppression.id).where(Suppression.email == message.sender_email)):
            db.add(Suppression(email=message.sender_email, reason="unsubscribe"))
            await audit(db, message, "inbound_unsubscribe_suppressed")
    if message.enrollment_id and (message.auto_submitted != "auto-generated" or category == "unsubscribe"):
        pause = await db.scalar(select(InboxPause).where(InboxPause.enrollment_id == message.enrollment_id, InboxPause.inbound_message_id == message.id))
        if not pause:
            reason = "unsubscribe" if category == "unsubscribe" else "out_of_office" if category == "out_of_office" else "human_reply"
            enrollment = await scoped_record(db, Enrollment, message.enrollment_id)
            await db.refresh(enrollment)
            if enrollment.status != "cancelled":
                enrollment.status = "paused"
            db.add(InboxPause(enrollment_id=enrollment.id, inbound_message_id=message.id, reason=reason))
            await audit(db, message, "inbound_sequence_held", {"enrollment_id": str(enrollment.id), "reason": reason})


async def reply_parent(db, sender_id, event):
    if not event.in_reply_to:
        return None
    return await db.scalar(select(InboundMessage).where(
        InboundMessage.sender_id == sender_id,
        InboundMessage.provider_message_id == event.in_reply_to,
        InboundMessage.sender_email == address(event.sender_email)))


async def associate(db, sender, thread, event):
    query = select(Message, MessageDraft).join(MessageDraft, MessageDraft.id == Message.draft_id).where(
        Message.state == "sent", MessageDraft.envelope["sender_id"].as_string() == str(sender.id))
    if event.in_reply_to:
        query = query.where(Message.provider_message_id == event.in_reply_to)
    else:
        query = query.join(InboxThreadLink, InboxThreadLink.outbound_message_id == Message.id).where(InboxThreadLink.thread_id == thread.id)
    candidates = (await db.execute(query)).all()
    if not candidates and event.in_reply_to:
        previous = await reply_parent(db, sender.id, event)
        if previous and previous.outbound_message_id:
            candidates = (await db.execute(select(Message, MessageDraft).join(MessageDraft, MessageDraft.id == Message.draft_id).where(
                Message.id == previous.outbound_message_id, Message.state == "sent",
                MessageDraft.envelope["sender_id"].as_string() == str(sender.id)))).all()
    if len(candidates) != 1:
        return {}, "ambiguous" if candidates else "unassociated"
    outbound, draft = candidates[0]
    if draft.envelope["recipient"] != address(event.sender_email):
        return {}, "sender_mismatch"
    scheduled = await scoped_record(db, ScheduledMessage, outbound.scheduled_id)
    data = {key: UUID(draft.envelope[key]) for key in ("contact_id", "company_id", "campaign_id", "sequence_id", "sequence_version_id", "brain_version_id", "research_job_id")}
    data.update(outbound_message_id=outbound.id, enrollment_id=scheduled.enrollment_id)
    if not await db.scalar(select(InboxThreadLink.id).where(InboxThreadLink.thread_id == thread.id, InboxThreadLink.outbound_message_id == outbound.id)):
        db.add(InboxThreadLink(thread_id=thread.id, outbound_message_id=outbound.id))
    return data, "linked"


async def ingest(db, sender_id, event: InboundEvent):
    """No caller-supplied workspace; resolve authenticated mailbox in bound DB."""
    await lock_workspace(db)
    sender = await scoped_record(db, SenderIdentity, sender_id)
    if address(event.recipient_email) != address(sender.email):
        raise HTTPException(409, "Inbound recipient does not match the authenticated mailbox")
    payload = event.model_dump(mode="json", exclude={"provider_event_id"})
    payload.update(sender_email=address(event.sender_email), recipient_email=address(event.recipient_email))
    content_hash = digest(payload)
    receipt = await db.scalar(select(InboundReceipt).where(InboundReceipt.sender_id == sender.id, InboundReceipt.provider_event_id == event.provider_event_id))
    if receipt:
        if receipt.content_hash != content_hash:
            raise HTTPException(409, "Provider event identity conflicts with its stored payload")
        return await scoped_record(db, InboundMessage, receipt.inbound_message_id)
    message = await db.scalar(select(InboundMessage).where(InboundMessage.sender_id == sender.id, InboundMessage.provider_message_id == event.provider_message_id))
    if message and message.content_hash != content_hash:
        raise HTTPException(409, "Provider message identity conflicts with its stored payload")
    if not message:
        thread_key = "thread:" + event.provider_thread_id if event.provider_thread_id else "message:" + event.provider_message_id
        thread = await db.scalar(select(InboxThread).where(InboxThread.sender_id == sender.id, InboxThread.thread_key == thread_key))
        if not thread and not event.provider_thread_id:
            previous = await reply_parent(db, sender.id, event)
            if previous:
                thread = await scoped_record(db, InboxThread, previous.thread_id)
        if not thread:
            thread = InboxThread(sender_id=sender.id, provider_thread_id=event.provider_thread_id, thread_key=thread_key)
            db.add(thread)
            await db.flush()
        linkage, association = await associate(db, sender, thread, event)
        received = event.received_at or datetime.now(timezone.utc)
        if received.tzinfo:
            received = received.astimezone(timezone.utc).replace(tzinfo=None)
        message = InboundMessage(thread_id=thread.id, sender_id=sender.id, provider_message_id=event.provider_message_id,
            in_reply_to=event.in_reply_to, sender_email=payload["sender_email"], recipient_email=payload["recipient_email"],
            subject=event.subject, body=event.body, auto_submitted=event.auto_submitted, received_at=received,
            content_hash=content_hash, association=association, **linkage)
        db.add(message)
        await db.flush()
        preliminary = classify(message.subject, message.body, message.auto_submitted)
        await protect_reply(db, message, preliminary.category)
        work = await audit(db, message, "inbound_received", {"association": association})
        work.due_at = datetime.utcnow()
    db.add(InboundReceipt(sender_id=sender.id, provider_event_id=event.provider_event_id, content_hash=content_hash, inbound_message_id=message.id))
    await db.commit()
    return message


async def latest_classification(db, message_id):
    return await db.scalar(select(ReplyClassification).where(ReplyClassification.inbound_message_id == message_id).order_by(ReplyClassification.number.desc()).limit(1))


async def classify_message(db, message):
    current = await latest_classification(db, message.id)
    if current:
        return current  # A manual review made before the worker must win.
    decision = Classification.model_validate(classify(message.subject, message.body, message.auto_submitted))
    row = ReplyClassification(inbound_message_id=message.id, number=1, **decision.model_dump())
    db.add(row)
    await protect_reply(db, message, decision.category)
    await audit(db, message, "inbound_classified", {"category": decision.category, "classifier": decision.classifier_version})
    return row


async def override(db, message, ctx, category, reason, expected_number):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    previous = await latest_classification(db, message.id)
    number = previous.number if previous else 0
    if number != expected_number:
        raise HTTPException(409, "Review the latest classification before overriding")
    row = ReplyClassification(inbound_message_id=message.id, number=number + 1, category=category,
        confidence=None, reason=reason, evidence=["Workspace administrator review"], classifier_version="manual-review-v1",
        recommended_action=ACTIONS[category], requires_review=False, manual_override=True, overridden_by=ctx.user_id)
    db.add(row)
    await protect_reply(db, message, category)
    await audit(db, message, "inbound_classification_overridden", {"category": category, "actor": str(ctx.user_id), "previous_number": number})
    await db.commit()
    return row


async def suggest(db, message, ctx):
    ctx.require("owner", "admin", "member")
    await lock_workspace(db)
    classification = await latest_classification(db, message.id)
    if not classification:
        raise HTTPException(409, "Wait for classification or review the message first")
    if classification.category in {"unsubscribe", "negative", "wrong_person", "out_of_office"} or await db.scalar(select(Suppression.id).where(Suppression.email == message.sender_email)):
        raise HTTPException(409, "This reply needs review without a response draft")
    current = await db.scalar(select(SuggestedReplyDraft).where(SuggestedReplyDraft.inbound_message_id == message.id, SuggestedReplyDraft.classification_id == classification.id))
    if current:
        return current
    context = {"thread_id": str(message.thread_id), "source_inbound_message_id": str(message.id), "classification_id": str(classification.id), "method": "review_template", "automatic_send": False}
    if message.outbound_message_id:
        outbound = await scoped_record(db, Message, message.outbound_message_id)
        draft = await scoped_record(db, MessageDraft, outbound.draft_id)
        context["prior_outreach"] = draft.envelope
        context["outbound_message_id"] = str(outbound.id)
    body = "Thank you for your reply. Could you share more about what you would like to discuss?"
    if classification.category == "meeting_intent":
        body = "Thank you for your interest in a conversation. What times and time zone would work for you?"
    elif classification.category == "objection":
        body = "Thank you for sharing your concern. Could you tell me more so I can respond appropriately?"
    row = SuggestedReplyDraft(inbound_message_id=message.id, classification_id=classification.id,
        subject=("Re: " + message.subject)[:500], body=body, context=context, created_by=ctx.user_id)
    db.add(row)
    await audit(db, message, "inbound_reply_draft_created", {"actor": str(ctx.user_id)})
    await db.commit()
    return row


async def processing_state(db, message):
    event = await db.scalar(select(DomainEvent).where(DomainEvent.kind == "inbound_received", DomainEvent.data["inbound_message_id"].as_string() == str(message.id)))
    work = await db.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event.id)) if event else None
    return {"status": work.status, "attempts": work.attempts, "error_code": work.error_code} if work else {"status": "missing", "attempts": 0, "error_code": "missing_ingestion_event"}
