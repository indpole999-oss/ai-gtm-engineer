"""Draft-only review transitions. No provider calls or execution commands."""
import hashlib
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from backend.outreach_models import DraftReviewEvent, MessageDraft, Message, ScheduledMessage
from backend.research_models import ResearchClaim, EvidenceItem, SourceFetch, AccountIntelligence, ClaimVerification
from backend.brain_models import BrainClaim
from backend.research_service import scoped_record
from backend.planning_service import digest


async def latest_event(db, scheduled_id):
    return await db.scalar(select(DraftReviewEvent).where(DraftReviewEvent.scheduled_id == scheduled_id)
        .order_by(DraftReviewEvent.revision.desc()).limit(1))


async def latest_draft(db, scheduled_id):
    event = await latest_event(db, scheduled_id)
    if event:
        return await scoped_record(db, MessageDraft, event.draft_id)
    return await db.scalar(select(MessageDraft).where(MessageDraft.scheduled_id == scheduled_id)
        .order_by(MessageDraft.created_at.desc(), MessageDraft.id.desc()).limit(1))


async def record(db, draft, actor, action, reason=""):
    event = await latest_event(db, draft.scheduled_id)
    row = DraftReviewEvent(scheduled_id=draft.scheduled_id, draft_id=draft.id,
        revision=event.revision + 1 if event else 1, action=action,
        actor_id=actor, content_hash=draft.content_hash, reason=reason)
    db.add(row)
    await db.flush()
    return row


async def status(db, draft):
    event = await latest_event(db, draft.scheduled_id)
    message = await db.scalar(select(Message).where(Message.scheduled_id == draft.scheduled_id))
    state = "approved" if message else "draft"
    if event and not message:
        state = "draft" if event.action in {"created", "revised"} else event.action
    return {"status": state, "revision": event.revision if event else 0,
        "current_draft_id": str(event.draft_id) if event else str((await latest_draft(db, draft.scheduled_id)).id)}


async def require_current(db, draft, expected_hash, revision):
    if draft.content_hash != expected_hash or digest(draft.envelope) != expected_hash:
        raise HTTPException(409, "Review the exact current draft")
    state = await status(db, draft)
    if state["current_draft_id"] != str(draft.id):
        raise HTTPException(409, "A newer draft exists; reload before reviewing")
    if revision != state["revision"]:
        raise HTTPException(409, "Review state changed; reload before acting")
    return state


async def references(db, draft):
    claim = await scoped_record(db, ResearchClaim, UUID(draft.envelope["research_claim_id"]))
    evidence = await scoped_record(db, EvidenceItem, claim.evidence_id)
    source = await scoped_record(db, SourceFetch, evidence.fetch_id)
    brain_claim = await scoped_record(db, BrainClaim, UUID(draft.envelope["brain_claim_id"]))
    return claim, evidence, source, brain_claim


async def validate(db, draft):
    from backend.outreach_service import context, unsuppressed, address
    if digest(draft.envelope) != draft.content_hash:
        raise HTTPException(409, "Draft content hash mismatch")
    scheduled = await scoped_record(db, ScheduledMessage, draft.scheduled_id)
    enrollment, step, version, sequence, campaign, contact, sender, job, brain = await context(db, scheduled)
    await unsuppressed(db, contact.email)
    claim, evidence, source, brain_claim = await references(db, draft)
    report = await db.scalar(select(AccountIntelligence).where(AccountIntelligence.job_id == job.id))
    from backend.pipeline_service import buyer_supported
    if not report or report.result.get("fit") != "potential_fit" or not buyer_supported(report.result.get("buyers", []), contact):
        raise HTTPException(409, "Source-backed account fit and matching buyer qualification required")
    expected = {"recipient": address(contact.email), "sender": address(sender.email),
        "contact_id": str(contact.id), "company_id": str(contact.company_id),
        "research_job_id": str(job.id), "evidence_id": str(evidence.id),
        "brain_version_id": str(brain.id), "brain_hash": brain.content_hash,
        "account_intelligence_id": str(report.id), "sequence_version_id": str(version.id),
        "sequence_hash": version.content_hash, "sequence_step_id": str(step.id), "sender_id": str(sender.id),
        "campaign_id": str(campaign.id), "sequence_id": str(sequence.id)}
    if any(draft.envelope.get(key) != value for key, value in expected.items()):
        raise HTTPException(409, "Draft references changed; prepare and review again")
    if (claim.job_id != job.id or claim.kind != "provider_assertion" or source.job_id != job.id
        or claim.text != evidence.excerpt or not evidence.excerpt or evidence.excerpt not in source.content
        or hashlib.sha256(source.content.encode()).hexdigest() != source.content_hash
        or brain_claim.version_id != brain.id or brain_claim.disposition != "approved"):
        raise HTTPException(409, "Draft claims are not supported by persisted source evidence")
    verification = await db.scalar(select(ClaimVerification).where(ClaimVerification.claim_id == claim.id)
        .order_by(ClaimVerification.created_at.desc(), ClaimVerification.id.desc()).limit(1))
    if verification and verification.decision != "verified":
        raise HTTPException(409, "Research claim was rejected by review")
    prohibited = (await db.scalars(select(BrainClaim.text).where(
        BrainClaim.version_id == brain.id, BrainClaim.disposition == "prohibited"))).all()
    text = draft.envelope["subject"] + "\n" + draft.envelope["body"]
    if any(value.casefold() in text.casefold() for value in prohibited):
        raise HTTPException(409, "Draft conflicts with a prohibited Company Brain claim")
    if claim.text not in draft.envelope["body"] or brain_claim.text not in draft.envelope["body"]:
        raise HTTPException(409, "Keep the source quotation and approved Company Brain claim intact")


async def describe(db, draft):
    state = await status(db, draft)
    history = (await db.scalars(select(DraftReviewEvent).where(DraftReviewEvent.scheduled_id == draft.scheduled_id)
        .order_by(DraftReviewEvent.revision))).all()
    claim, evidence, source, brain_claim = await references(db, draft)
    return {**state, "history": [{"id": str(x.id), "draft_id": str(x.draft_id), "revision": x.revision,
        "action": x.action, "actor_id": str(x.actor_id), "created_at": x.created_at,
        "content_hash": x.content_hash, "reason": x.reason} for x in history],
        "evidence": {"excerpt": evidence.excerpt, "claim": claim.text, "source_url": source.url,
            "source_hash": source.content_hash, "brain_claim": brain_claim.text},
        "warnings": ["Edited wording outside the quoted evidence and approved Company Brain claim is not verified. Review every added assertion."] if draft.envelope.get("composition_method") == "human_edited" else []}


async def revise(db, draft, ctx, expected_hash, revision, subject, body):
    from backend.outreach_service import lock_workspace
    ctx.require("owner", "admin", "member")
    await lock_workspace(db)
    # A replay of an identical edit returns the already-persisted revision.
    current = await latest_draft(db, draft.scheduled_id)
    if (current.envelope.get("parent_draft_id") == str(draft.id)
        and current.envelope["subject"] == subject and current.envelope["body"] == body
        and draft.content_hash == expected_hash):
        return current
    state = await require_current(db, draft, expected_hash, revision)
    if state["status"] not in {"draft", "rejected", "changes_requested"}:
        raise HTTPException(409, "Only unsubmitted drafts can be edited")
    if subject == draft.envelope["subject"] and body == draft.envelope["body"]:
        return draft
    envelope = {**draft.envelope, "subject": subject, "body": body,
        "composition_method": "human_edited", "parent_draft_id": str(draft.id)}
    row = MessageDraft(scheduled_id=draft.scheduled_id, envelope=envelope,
        content_hash=digest(envelope), created_by=ctx.user_id)
    await validate(db, row)
    db.add(row)
    await db.flush()
    await record(db, row, ctx.user_id, "revised")
    await db.commit()
    return row


async def transition(db, draft, ctx, expected_hash, revision, action, reason=""):
    from backend.outreach_service import lock_workspace
    ctx.require(*(["owner", "admin", "member"] if action == "submitted" else ["owner", "admin"]))
    await lock_workspace(db)
    # Same transition against its original revision is idempotent, not a second audit.
    event = await latest_event(db, draft.scheduled_id)
    if (event and event.draft_id == draft.id and event.action == action and event.reason == reason
        and event.content_hash == expected_hash and event.revision == revision + 1
        and event.actor_id == ctx.user_id):
        return draft
    state = await require_current(db, draft, expected_hash, revision)
    if action == "submitted":
        if state["status"] != "draft":
            raise HTTPException(409, "Revise the draft before submitting again")
        await validate(db, draft)
    elif state["status"] != "submitted":
        raise HTTPException(409, "Only submitted drafts can be reviewed")
    await record(db, draft, ctx.user_id, action, reason)
    await db.commit()
    return draft
