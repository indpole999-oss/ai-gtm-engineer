"""Composition and reviewed delivery; never calls a provider from an HTTP request."""
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from pydantic import TypeAdapter, EmailStr
from fastapi import HTTPException
from sqlalchemy import select
from backend.database import Contact, Workspace, WorkspaceMembership, User, Integration
from backend.brain_models import CompanyBrainVersion, BrainClaim
from backend.research_models import ResearchJob, ResearchClaim, EvidenceItem, SourceFetch, AccountIntelligence, ClaimVerification
from backend.research_service import scoped_record
from backend.planning_models import Goal, PlanVersion, ExecutionCycle, ActionCommand
from backend.planning_service import digest, PlanDocument, PlanStep
from backend.outreach_models import Campaign, Sequence, SequenceVersion, SequenceStep, SenderIdentity, Enrollment, ScheduledMessage, MessageDraft, Message, Suppression, DeliveryEvent


def address(value):
    try:
        return str(TypeAdapter(EmailStr).validate_python(value)).strip().lower()
    except ValueError:
        raise HTTPException(409, "A valid recipient/sender email is required") from None


async def lock_workspace(db):
    # Shared serialization boundary for approval, dispatch, limits and suppression.
    await db.scalar(select(Workspace).where(Workspace.id == db.info["workspace_id"]).with_for_update())


async def context(db, scheduled):
    enrollment = await scoped_record(db, Enrollment, scheduled.enrollment_id)
    step = await scoped_record(db, SequenceStep, scheduled.sequence_step_id)
    version = await scoped_record(db, SequenceVersion, enrollment.version_id)
    sequence = await scoped_record(db, Sequence, version.sequence_id)
    campaign = await scoped_record(db, Campaign, sequence.campaign_id)
    contact = await scoped_record(db, Contact, enrollment.contact_id)
    sender = await scoped_record(db, SenderIdentity, enrollment.sender_id)
    job = await scoped_record(db, ResearchJob, enrollment.research_job_id)
    brain = await scoped_record(db, CompanyBrainVersion, job.brain_version_id)
    if step.version_id != version.id or digest(version.definition) != version.content_hash:
        raise HTTPException(409, "Sequence version mismatch")
    definitions = version.definition.get("steps", [])
    if step.position < 0 or step.position >= len(definitions) or definitions[step.position] != {"delay_seconds": step.delay_seconds, "purpose": step.purpose}:
        raise HTTPException(409, "Sequence step does not match its immutable definition")
    if job.status != "completed" or job.company_id != contact.company_id or brain.status != "published":
        raise HTTPException(409, "Completed research for this contact and published Brain required")
    if enrollment.status != "active" or campaign.status != "active":
        raise HTTPException(409, "Outreach is paused")
    return enrollment, step, version, sequence, campaign, contact, sender, job, brain


async def unsuppressed(db, email):
    if await db.scalar(select(Suppression.id).where(Suppression.email == address(email))):
        raise HTTPException(409, "Recipient is suppressed or unsubscribed")


async def compose(db, scheduled, actor):
    enrollment, step, version, sequence, campaign, contact, sender, job, brain = await context(db, scheduled)
    await unsuppressed(db, contact.email)
    report = await db.scalar(select(AccountIntelligence).where(AccountIntelligence.job_id == job.id))
    claims = (await db.scalars(select(ResearchClaim).where(ResearchClaim.job_id == job.id, ResearchClaim.kind == "provider_assertion", ResearchClaim.evidence_id.is_not(None)).order_by(ResearchClaim.id))).all()
    approved_claims = (await db.scalars(select(BrainClaim).where(BrainClaim.version_id == brain.id, BrainClaim.disposition == "approved"))).all()
    if not report or not claims or not approved_claims:
        raise HTTPException(409, "Evidence and approved Company Brain claims required")
    # Deterministic, evidence-only composition. No invented claims or model/API call.
    claim = claims[0]
    review = await db.scalar(select(ClaimVerification).where(ClaimVerification.claim_id == claim.id).order_by(ClaimVerification.created_at.desc(), ClaimVerification.id.desc()).limit(1))
    if review and review.decision != "verified":
        raise HTTPException(409, "Research claim was rejected by review")
    evidence = await scoped_record(db, EvidenceItem, claim.evidence_id)
    source = await scoped_record(db, SourceFetch, evidence.fetch_id)
    if source.job_id != job.id:
        raise HTTPException(409, "Evidence belongs to another research job")
    body = f"Hello {contact.first_name or 'there'},\n\nYour website states: {claim.text}\n\n{approved_claims[0].text}\n\nWould a conversation be useful?\n\nTo opt out, reply unsubscribe."
    prohibited = (await db.scalars(select(BrainClaim.text).where(BrainClaim.version_id == brain.id, BrainClaim.disposition == "prohibited"))).all()
    if any(text.casefold() in body.casefold() for text in prohibited):
        raise HTTPException(409, "Draft conflicts with a prohibited Company Brain claim")
    envelope = {"recipient": address(contact.email), "sender": address(sender.email),
        "subject": "A question for your team", "body": body,
        "contact_id": str(contact.id), "company_id": str(contact.company_id), "research_job_id": str(job.id),
        "evidence_id": str(evidence.id), "research_claim_id": str(claim.id), "brain_claim_id": str(approved_claims[0].id),
        "brain_version_id": str(brain.id), "brain_hash": brain.content_hash,
        "account_intelligence_id": str(report.id), "buyer_reasoning": report.result,
        "campaign_id": str(campaign.id), "sequence_id": str(sequence.id), "sequence_version_id": str(version.id),
        "sequence_hash": version.content_hash, "sequence_step_id": str(step.id), "sender_id": str(sender.id),
        "due_at": scheduled.due_at.isoformat(), "composition_method": "evidence_template"}
    row = MessageDraft(scheduled_id=scheduled.id, envelope=envelope, content_hash=digest(envelope), created_by=actor)
    db.add(row)
    await db.commit()
    return row


async def approve_message(db, draft, ctx, expected_hash):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    if draft.content_hash != expected_hash or digest(draft.envelope) != expected_hash:
        raise HTTPException(409, "Review the exact current draft")
    existing = await db.scalar(select(Message).where(Message.scheduled_id == draft.scheduled_id))
    if existing:
        if existing.draft_id != draft.id:
            raise HTTPException(409, "Another draft is already approved for this step")
        return existing
    scheduled = await scoped_record(db, ScheduledMessage, draft.scheduled_id)
    *_, contact, sender, job, brain = await context(db, scheduled)
    await unsuppressed(db, contact.email)
    if draft.envelope["recipient"] != address(contact.email) or draft.envelope["sender"] != address(sender.email):
        raise HTTPException(409, "Recipient/sender changed; compose and review again")
    message_id = uuid4()
    goal = Goal(objective="Deliver the separately reviewed outreach message", brain_version_id=brain.id, created_by=ctx.user_id,
        target_inputs=[{"company_id": str(contact.company_id), "source_urls": job.source_urls}])
    db.add(goal)
    await db.flush()
    document = PlanDocument(objective=goal.objective, success_metrics=["Provider acceptance"], target_segment=brain.profile["icp"],
        constraints=["Approved immutable content only", "Suppression and sender limits", "Zero paid APIs"], assumptions=[],
        risks=["Provider outcome may require reconciliation"], steps=[PlanStep(action="outreach_send", message_id=message_id,
        target_index=0, rationale="Explicitly approved message", expected_output="Provider acceptance reference", side_effect="outbound")],
        stop_conditions=["Suppression", "Approval revoked", "Provider failure"], review_checkpoint="Review message and delivery state")
    envelope = {"plan": document.model_dump(mode="json"), "brain_version_id": str(brain.id), "brain_hash": brain.content_hash, "targets": goal.target_inputs}
    plan = PlanVersion(goal_id=goal.id, number=1, document=envelope, content_hash=digest(envelope), author_method="reviewed_outreach")
    db.add(plan)
    await db.flush()
    row = Message(id=message_id, draft_id=draft.id, scheduled_id=scheduled.id, approved_by=ctx.user_id, approved_hash=expected_hash, plan_id=plan.id)
    db.add(row)
    await db.commit()
    return row


async def valid_message(db, message, plan_id):
    draft = await scoped_record(db, MessageDraft, message.draft_id)
    if message.plan_id != plan_id or message.approved_hash != draft.content_hash or digest(draft.envelope) != message.approved_hash:
        raise HTTPException(409, "Message approval does not match the plan")
    active = await db.scalar(select(WorkspaceMembership).join(User, User.id == WorkspaceMembership.user_id).join(Workspace, Workspace.id == WorkspaceMembership.workspace_id).where(
        WorkspaceMembership.workspace_id == db.info["workspace_id"], WorkspaceMembership.user_id == message.approved_by,
        WorkspaceMembership.status == "active", WorkspaceMembership.role.in_(["owner", "admin"]), User.is_active.is_(True), Workspace.status == "active"))
    if not active:
        raise HTTPException(409, "Message approver is no longer authorized")
    review = await db.scalar(select(ClaimVerification).where(ClaimVerification.claim_id == UUID(draft.envelope["research_claim_id"])).order_by(ClaimVerification.created_at.desc(), ClaimVerification.id.desc()).limit(1))
    if review and review.decision != "verified":
        raise HTTPException(409, "Research claim is no longer approved for outreach")
    return draft


async def schedule_ready(db, scheduled):
    if scheduled.due_at > datetime.utcnow():
        return False
    enrollment = await scoped_record(db, Enrollment, scheduled.enrollment_id)
    version = await scoped_record(db, SequenceVersion, enrollment.version_id)
    sequence = await scoped_record(db, Sequence, version.sequence_id)
    campaign = await scoped_record(db, Campaign, sequence.campaign_id)
    if enrollment.status != "active" or campaign.status != "active":
        return False
    step = await scoped_record(db, SequenceStep, scheduled.sequence_step_id)
    earlier = (await db.scalars(select(ScheduledMessage).join(SequenceStep, SequenceStep.id == ScheduledMessage.sequence_step_id).where(ScheduledMessage.enrollment_id == scheduled.enrollment_id, SequenceStep.position < step.position))).all()
    for previous in earlier:
        prior = await db.scalar(select(Message).where(Message.scheduled_id == previous.id))
        if not prior or prior.state != "sent" or datetime.utcnow() < prior.accepted_at + timedelta(seconds=step.delay_seconds):
            return False
    return True


class DisabledProvider:
    """No external sends are enabled. Adapters must guarantee durable key deduplication."""
    durable_idempotency = False
    async def lookup(self, key):
        raise RuntimeError("Outbound provider disabled")

    async def send(self, key, envelope):
        raise RuntimeError("Outbound provider disabled")


def delivery_provider(sender):
    return DisabledProvider()


async def deliver(db, command, cycle):
    # Hold the workspace lock through the bounded provider call. Suppressions and
    # parallel workers cannot cross this dispatch boundary. Stable message ID is
    # the provider idempotency key, independent of command/lease/retry identity.
    token = command.lease_token
    await lock_workspace(db)
    await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == cycle.id).with_for_update().execution_options(populate_existing=True))
    await db.refresh(command)
    await db.refresh(cycle)
    if command.lease_token != token or command.status != "running" or cycle.status != "running":
        raise HTTPException(409, "Execution authorization changed")
    message = await scoped_record(db, Message, UUID(command.payload["message_id"]))
    draft = await valid_message(db, message, cycle.plan_id)
    if message.state == "sent":
        return {"message_id": str(message.id), "provider_message_id": message.provider_message_id}
    scheduled = await scoped_record(db, ScheduledMessage, message.scheduled_id)
    enrollment, step, version, sequence, campaign, contact, sender, job, brain = await context(db, scheduled)
    if datetime.utcnow() < scheduled.due_at:
        raise HTTPException(409, "Message is not due")
    provider = delivery_provider(sender)
    key = f"{message.workspace_id}:{message.id}"
    # Reconcile even if suppression arrived after an uncertain previous attempt.
    # Lookup has no send side effect. Never resubmit an unknown outcome blindly.
    try:
        if not getattr(provider, "durable_idempotency", False):
            raise RuntimeError("Provider has no durable idempotency guarantee")
        receipt = await provider.lookup(key)
    except Exception:
        message.state = "reconciling" if message.attempted_at else "failed"
        message.error_code = "provider_lookup_unavailable"
        await db.commit()
        raise
    if receipt is None:
        try:
            await unsuppressed(db, draft.envelope["recipient"])
            await unsuppressed(db, contact.email)
            if address(contact.email) != draft.envelope["recipient"] or address(sender.email) != draft.envelope["sender"]:
                raise HTTPException(409, "Recipient or sender changed")
            if sender.status != "connected":
                raise HTTPException(409, "Sender is not connected")
            if sender.provider != "fake":
                integration = await scoped_record(db, Integration, sender.integration_id)
                if integration.health != "healthy" or integration.provider != sender.provider:
                    raise HTTPException(409, "Sender connection invalid")
            earlier = (await db.scalars(select(ScheduledMessage).join(SequenceStep, SequenceStep.id == ScheduledMessage.sequence_step_id).where(ScheduledMessage.enrollment_id == enrollment.id, SequenceStep.position < step.position))).all()
            for previous in earlier:
                prior = await db.scalar(select(Message).where(Message.scheduled_id == previous.id))
                if not prior or prior.state != "sent" or datetime.utcnow() < prior.accepted_at + timedelta(seconds=step.delay_seconds):
                    raise HTTPException(409, "Previous sequence step has not completed its delay")
            # Count all persisted attempts, including uncertain/failing outcomes.
            rows = (await db.execute(select(Message, MessageDraft).join(MessageDraft, MessageDraft.id == Message.draft_id).where(Message.attempted_at >= datetime.utcnow() - timedelta(days=1), Message.id != message.id))).all()
            if sum(d.envelope["sender_id"] == str(sender.id) for m, d in rows) >= sender.daily_limit:
                raise HTTPException(409, "Sender daily limit reached")
            if any(d.envelope["recipient"] == draft.envelope["recipient"] for m, d in rows):
                raise HTTPException(409, "Recipient daily limit reached")
        except HTTPException:
            message.state, message.error_code = "blocked", "outreach_safeguard"
            await db.commit()
            raise
        message.state, message.attempted_at = "sending", datetime.utcnow()
        # Commit intent before crossing provider boundary. Reacquire lock and
        # recheck authorization/suppression after commit in dispatch below.
        await db.commit()
        await lock_workspace(db)
        await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == cycle.id).with_for_update().execution_options(populate_existing=True))
        await db.refresh(cycle)
        await db.refresh(command)
        from backend.execution_worker import approved
        if cycle.status != "running" or command.status != "running" or command.lease_token != token or command.lease_until <= datetime.utcnow() or not await approved(db, cycle):
            raise HTTPException(409, "Execution authorization changed")
        await valid_message(db, message, cycle.plan_id)
        await unsuppressed(db, draft.envelope["recipient"])
        await db.refresh(sender, with_for_update=True)
        await db.refresh(contact, with_for_update=True)
        await db.refresh(enrollment)
        await db.refresh(campaign)
        await db.refresh(job)
        await context(db, scheduled)
        if sender.status != "connected" or address(contact.email) != draft.envelope["recipient"] or address(sender.email) != draft.envelope["sender"]:
            raise HTTPException(409, "Sender or recipient changed")
        if sender.provider != "fake":
            integration = await scoped_record(db, Integration, sender.integration_id)
            await db.refresh(integration, with_for_update=True)
            if integration.health != "healthy" or integration.status != "connected" or integration.provider != sender.provider or integration.reconnect_required:
                raise HTTPException(409, "Sender connection changed")
        try:
            receipt = await provider.send(key, draft.envelope)
        except Exception:
            message.state, message.error_code = "reconciling", "provider_outcome_unknown"
            await db.commit()
            raise
    if not isinstance(receipt, dict) or receipt.get("status") != "accepted" or not isinstance(receipt.get("id"), str) or not receipt["id"]:
        message.state, message.error_code = "failed", "provider_not_accepted"
        await db.commit()
        raise ValueError("Provider did not confirm acceptance")
    message.state, message.provider_message_id, message.accepted_at, message.error_code = "sent", receipt["id"], datetime.utcnow(), None
    db.add(DeliveryEvent(message_id=message.id, provider_event_id=key + ":accepted", kind="accepted"))
    await db.commit()
    return {"message_id": str(message.id), "provider_message_id": message.provider_message_id}


async def record_delivery_event(db, message_id, provider_message_id, event_id, kind):
    """Trusted adapter entry point only; never accept unauthenticated webhooks."""
    if kind not in {"delivered", "bounce", "complaint", "unsubscribe"}:
        raise ValueError("Unsupported delivery event")
    await lock_workspace(db)
    message = await scoped_record(db, Message, message_id)
    if message.state != "sent" or message.provider_message_id != provider_message_id:
        raise HTTPException(409, "Provider event does not match an accepted message")
    previous = await db.scalar(select(DeliveryEvent).where(DeliveryEvent.provider_event_id == event_id))
    if previous:
        if previous.message_id != message.id or previous.kind != kind:
            raise HTTPException(409, "Provider event identity conflict")
        return previous
    row = DeliveryEvent(message_id=message.id, provider_event_id=event_id, kind=kind)
    db.add(row)
    if kind in {"bounce", "complaint", "unsubscribe"}:
        draft = await scoped_record(db, MessageDraft, message.draft_id)
        email = draft.envelope["recipient"]
        if not await db.scalar(select(Suppression.id).where(Suppression.email == email)):
            db.add(Suppression(email=email, reason=kind))
    await db.commit()
    return row
