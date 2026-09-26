"""Evidence-backed stage history. Caller serializes changes with workspace lock."""
from uuid import UUID
from sqlalchemy import select
from fastapi import HTTPException
from backend.database import Company, Contact
from backend.outcome_models import PipelineRecord, PipelineHistory, STAGES
from backend.research_service import scoped_record
from backend.planning_service import emit


async def ensure(db, company_id, contact_id=None, actor=None):
    company = await scoped_record(db, Company, company_id)
    if contact_id:
        contact = await scoped_record(db, Contact, contact_id)
        if contact.company_id != company.id:
            raise HTTPException(409, "Contact does not belong to the pipeline account")
    key = "contact:" + str(contact_id) if contact_id else "company:" + str(company_id)
    row = await db.scalar(select(PipelineRecord).where(PipelineRecord.record_key == key))
    if row:
        if row.company_id != company_id:
            raise HTTPException(409, "Historical prospect account association cannot be replaced")
        return row
    row = PipelineRecord(company_id=company_id, contact_id=contact_id, record_key=key, stage="discovered", revision=1)
    db.add(row)
    await db.flush()
    db.add(PipelineHistory(pipeline_id=row.id, source_key="discovered", from_stage=None, to_stage="discovered",
        source="persisted_record", actor_id=actor, reason="Account/prospect persisted in this workspace", evidence={"record": key}))
    await emit(db, None, "pipeline_discovered", {"pipeline_id": str(row.id)})
    return row


async def transition(db, row, stage, source, source_key, reason, actor=None, evidence=None, cycle=None, campaign_id=None, version_id=None, manual=False):
    if stage not in STAGES:
        raise HTTPException(422, "Unknown pipeline stage")
    if await db.scalar(select(PipelineHistory.id).where(PipelineHistory.pipeline_id == row.id, PipelineHistory.source_key == source_key)):
        return row
    await db.refresh(row)
    applied = manual or (row.stage not in {"opportunity", "won", "lost"} and STAGES.index(stage) > STAGES.index(row.stage))
    before = row.stage
    if applied:
        row.stage, row.revision = stage, row.revision + 1
    db.add(PipelineHistory(pipeline_id=row.id, source_key=source_key, from_stage=before, to_stage=stage,
        applied=applied, source=source, reason=reason, actor_id=actor, evidence=evidence or {},
        cycle_id=cycle.id if cycle else None, campaign_id=campaign_id, sequence_version_id=version_id))
    await emit(db, cycle, "pipeline_stage_evaluated", {"pipeline_id": str(row.id), "from": before, "to": stage, "applied": applied, "source_key": source_key})
    return row


async def qualification(db, job):
    from backend.research_models import AccountIntelligence
    report = await db.scalar(select(AccountIntelligence).where(AccountIntelligence.job_id == job.id))
    if job.status != "completed" or not report or report.result.get("fit") != "potential_fit":
        return
    rows = [await ensure(db, job.company_id)]
    for contact in (await db.scalars(select(Contact).where(Contact.company_id == job.company_id))).all():
        rows.append(await ensure(db, job.company_id, contact.id))
    for row in rows:
        await transition(db, row, "qualified", "research", "research:" + str(job.id), "Persisted ICP potential-fit qualification; not independent verification",
            evidence={"research_job_id": str(job.id), "brain_version_id": str(job.brain_version_id)})


async def outbound(db, message, draft, cycle):
    if message.state != "sent" or not message.provider_message_id:
        raise HTTPException(409, "Provider-confirmed send required")
    row = await ensure(db, UUID(draft.envelope["company_id"]), UUID(draft.envelope["contact_id"]))
    await transition(db, row, "contacted", "outbound", "outbound:" + str(message.id), "Provider confirmed outbound acceptance",
        evidence={"message_id": str(message.id)}, cycle=cycle, campaign_id=UUID(draft.envelope["campaign_id"]), version_id=UUID(draft.envelope["sequence_version_id"]))


async def inbound(db, message, classification=None):
    if not message.contact_id or message.auto_submitted != "no":
        return
    row = await ensure(db, message.company_id, message.contact_id)
    from backend.inbox_service import message_cycle
    cycle = await message_cycle(db, message)
    # Explicit absence is not human engagement, even without an auto header.
    from backend.inbox_classifier import classify
    category = classification.category if classification else classify(message.subject, message.body, message.auto_submitted).category
    if category == "out_of_office":
        return
    await transition(db, row, "engaged", "inbound", "inbound:" + str(message.id), "Stored linked human reply",
        evidence={"inbound_message_id": str(message.id)}, cycle=cycle, campaign_id=message.campaign_id, version_id=message.sequence_version_id)
    if classification and category in {"positive", "meeting_intent"}:
        await transition(db, row, "interested", "classification", "classification:" + str(classification.id), "Reply evidence supports interest; no meeting inferred",
            evidence={"classification_id": str(classification.id), "inbound_message_id": str(message.id)}, cycle=cycle,
            campaign_id=message.campaign_id, version_id=message.sequence_version_id)


async def manual(db, row, ctx, stage, expected_revision, reason, evidence_kind=None, evidence_id=None):
    ctx.require("owner", "admin")
    await db.refresh(row)
    if row.revision != expected_revision:
        raise HTTPException(409, "Review the current pipeline revision")
    evidence = {}
    if stage == "qualified":
        from backend.research_models import ResearchJob, AccountIntelligence
        job = await scoped_record(db, ResearchJob, evidence_id) if evidence_kind == "research" and evidence_id else None
        report = await db.scalar(select(AccountIntelligence).where(AccountIntelligence.job_id == job.id)) if job else None
        if not job or job.company_id != row.company_id or job.status != "completed" or not report or report.result.get("fit") != "potential_fit":
            raise HTTPException(409, "Supported qualification required")
    elif stage == "contacted":
        from backend.outreach_models import Message, MessageDraft
        message = await scoped_record(db, Message, evidence_id) if evidence_kind == "outbound" and evidence_id else None
        draft = await scoped_record(db, MessageDraft, message.draft_id) if message else None
        if not message or message.state != "sent" or not message.provider_message_id or draft.envelope["company_id"] != str(row.company_id) or (row.contact_id and draft.envelope["contact_id"] != str(row.contact_id)):
            raise HTTPException(409, "Matching provider-confirmed send required")
    elif stage in {"engaged", "interested"}:
        from backend.inbox_models import InboundMessage
        from backend.inbox_service import latest_classification
        message = await scoped_record(db, InboundMessage, evidence_id) if evidence_kind == "inbound" and evidence_id else None
        classification = await latest_classification(db, message.id) if message else None
        if not message or message.company_id != row.company_id or (row.contact_id and message.contact_id != row.contact_id) or message.auto_submitted != "no" or not classification or classification.category == "out_of_office" or (stage == "interested" and classification.category not in {"positive", "meeting_intent"}):
            raise HTTPException(409, "Matching classified human reply required")
    elif stage == "meeting":
        from backend.outcome_models import OutcomeAction
        action = await scoped_record(db, OutcomeAction, evidence_id) if evidence_kind == "calendar" and evidence_id else None
        if not action or action.pipeline_id != row.id or action.kind != "calendar_schedule" or action.state != "confirmed" or not action.external_id:
            raise HTTPException(409, "Provider-confirmed meeting required")
    elif stage in {"opportunity", "won", "lost"} and evidence_kind != "explicit_user":
        raise HTTPException(409, "Explicit reviewed business outcome required")
    evidence.update(kind=evidence_kind, id=str(evidence_id) if evidence_id else None)
    return await transition(db, row, stage, "manual_review", "manual:" + str(expected_revision), reason, actor=ctx.user_id, evidence=evidence, manual=True)
