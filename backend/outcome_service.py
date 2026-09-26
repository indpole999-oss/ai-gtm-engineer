"""Reviewable CRM/calendar requests executed exclusively by Phase 5 commands."""
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from backend.database import Company, Contact, Integration, IntegrationAudit, CRMRecord
from backend.brain_models import CompanyBrainVersion
from backend.outcome_models import PipelineRecord, CRMMapping, OutcomeAction, CalendarBooking, CRMReceipt
from backend.planning_models import Goal, PlanVersion, ExecutionCycle, ActionCommand
from backend.planning_service import PlanDocument, PlanStep, digest, emit
from backend.research_service import scoped_record
from backend.outreach_service import lock_workspace, address, unsuppressed
from backend.inbox_models import InboundMessage
from backend.inbox_service import latest_classification
from backend import pipeline_service, outcome_providers, integration_service
from backend.providers import ProviderError


class CRMInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipeline_id: UUID
    integration_id: UUID
    brain_version_id: UUID
    request_key: str = Field(min_length=8, max_length=255)
    object_type: Literal["company", "contact", "opportunity"]
    expected_mapping_revision: int = Field(default=0, ge=0)
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    remote_version: str | None = Field(default=None, min_length=1, max_length=255)
    deal_pipeline_id: str | None = Field(default=None, min_length=1, max_length=255)
    deal_stage_id: str | None = Field(default=None, min_length=1, max_length=255)


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipeline_id: UUID
    integration_id: UUID
    brain_version_id: UUID
    request_key: str = Field(min_length=8, max_length=255)
    inbound_message_id: UUID
    classification_id: UUID
    title: str = Field(min_length=1, max_length=500)
    attendees: list[EmailStr] = Field(min_length=1, max_length=20)
    timezone: str = Field(min_length=1, max_length=100)
    start: datetime
    end: datetime


async def binding(db, integration):
    # Reconnect/account edits invalidate approval; routine OAuth token refresh does not.
    generations = (await db.scalars(select(IntegrationAudit.id).where(IntegrationAudit.integration_id == integration.id,
        IntegrationAudit.action.in_(["connection_created", "connection_updated", "connection_revoked", "oauth_connected"])))).all()
    return digest({"provider": integration.provider, "category": integration.category, "config": integration.config,
        "generations": sorted(str(i) for i in generations), "legacy_binding": None if generations else digest(integration.credentials)})


async def healthy(db, integration_id, kind):
    row = await scoped_record(db, Integration, integration_id)
    await db.refresh(row, with_for_update=True)
    expected = "crm" if kind == "crm_sync" else "calendar"
    if row.category != expected or row.status != "connected" or row.health != "healthy" or row.reconnect_required:
        raise HTTPException(409, "A healthy matching workspace integration is required")
    if (expected == "crm" and row.provider != "hubspot") or (expected == "calendar" and row.provider != "google"):
        raise HTTPException(409, "This provider does not implement safe outcome writes")
    if expected == "calendar" and integration_service.GOOGLE_SCOPE not in (row.scopes or []):
        raise HTTPException(409, "Google Calendar authorization scope is required")
    return row


async def duplicate_request(db, request_key, input_hash):
    row = await db.scalar(select(OutcomeAction).where(OutcomeAction.request_key == request_key))
    if row and row.payload["input_hash"] != input_hash:
        raise HTTPException(409, "Request identity already belongs to a different payload")
    return row


async def create_action(db, ctx, body, kind):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    input_hash = digest(body.model_dump(mode="json"))
    existing = await duplicate_request(db, body.request_key, input_hash)
    if existing:
        return existing
    pipeline = await scoped_record(db, PipelineRecord, body.pipeline_id)
    integration = await healthy(db, body.integration_id, kind)
    brain = await scoped_record(db, CompanyBrainVersion, body.brain_version_id)
    if brain.status != "published" or not brain.content_hash:
        raise HTTPException(409, "Published Company Brain required")
    action_id = uuid4()
    payload = {"input_hash": input_hash, "integration_binding": await binding(db, integration),
        "provider": integration.provider, "pipeline_revision": pipeline.revision,
        "brain_version_id": str(brain.id), "company_id": str(pipeline.company_id), "contact_id": str(pipeline.contact_id) if pipeline.contact_id else None}
    mapping = None
    booking_fields = None
    if kind == "crm_sync":
        if body.object_type == "company" and pipeline.contact_id:
            raise HTTPException(409, "Company sync must use the account pipeline record")
        if body.object_type == "contact" and not pipeline.contact_id:
            raise HTTPException(409, "Contact sync requires a prospect pipeline record")
        if body.object_type == "opportunity" and (pipeline.contact_id or pipeline.stage not in {"opportunity", "won", "lost"}):
            raise HTTPException(409, "Opportunity sync requires an explicit account business outcome")
        mapping = await db.scalar(select(CRMMapping).where(CRMMapping.integration_id == integration.id, CRMMapping.pipeline_id == pipeline.id, CRMMapping.object_type == body.object_type))
        if mapping and mapping.revision != body.expected_mapping_revision or not mapping and body.expected_mapping_revision != 0:
            raise HTTPException(409, "Review the current CRM mapping revision")
        if not mapping:
            if body.object_type == "contact":
                legacy = (await db.scalars(select(CRMRecord).where(CRMRecord.contact_id == pipeline.contact_id, CRMRecord.provider == integration.provider))).all()
                known = {r.external_id or r.crm_id for r in legacy if r.external_id or r.crm_id}
                if known and (not body.external_id or body.external_id not in known):
                    raise HTTPException(409, "Existing CRM identity requires explicit reviewed mapping and remote revision; do not create another contact")
            if bool(body.external_id) != bool(body.remote_version):
                raise HTTPException(409, "Existing external ID requires its reviewed remote revision")
            if body.external_id and await db.scalar(select(CRMMapping.id).where(CRMMapping.integration_id == integration.id, CRMMapping.object_type == body.object_type, CRMMapping.external_id == body.external_id)):
                raise HTTPException(409, "External object is already mapped")
            mapping = CRMMapping(integration_id=integration.id, pipeline_id=pipeline.id, object_type=body.object_type,
                provider=integration.provider, external_id=body.external_id, remote_version=body.remote_version)
            db.add(mapping)
            await db.flush()
        elif (body.external_id and body.external_id != mapping.external_id) or (body.remote_version and body.remote_version != mapping.remote_version):
            raise HTTPException(409, "Cannot replace a stored mapping through sync")
        pending = await db.scalar(select(OutcomeAction.id).where(OutcomeAction.mapping_id == mapping.id, OutcomeAction.state.in_(["draft", "sending", "reconciling", "failed"])))
        if pending:
            raise HTTPException(409, "Reconcile the existing operation before creating another sync")
        if body.object_type == "opportunity" and (not body.deal_pipeline_id or not body.deal_stage_id):
            raise HTTPException(409, "Explicit provider deal pipeline and stage IDs required; no stage IDs are inferred")
        if body.object_type != "opportunity" and (body.deal_pipeline_id or body.deal_stage_id):
            raise HTTPException(422, "Deal IDs apply only to opportunities")
        properties = await crm_properties(db, pipeline, body.object_type)
        if body.object_type == "opportunity":
            properties.update(pipeline=body.deal_pipeline_id, dealstage=body.deal_stage_id)
        payload.update(object_type=body.object_type, properties=properties, external_id=mapping.external_id,
            remote_version=mapping.remote_version, mapping_revision=mapping.revision, local_key=str(mapping.id))
    else:
        message, classification = await intent(db, pipeline, body.inbound_message_id, body.classification_id)
        start, end = normalize_times(body.start, body.end, body.timezone)
        attendees = sorted(set(address(e) for e in body.attendees))
        if message.sender_email not in attendees:
            raise HTTPException(409, "The supported reply sender must be an attendee")
        for email in attendees:
            await unsuppressed(db, email)
        calendar_id = (integration.config or {}).get("calendar_id") or "primary"
        duplicate_key = digest({"attendees": attendees, "start": start.isoformat(), "end": end.isoformat()})
        bookings = (await db.scalars(select(CalendarBooking).where(CalendarBooking.start_at < end, CalendarBooking.end_at > start))).all()
        if any(set(b.attendees) & set(attendees) for b in bookings):
            raise HTTPException(409, "An overlapping scheduling request already reserves an attendee")
        payload.update(title=body.title, attendees=attendees, timezone=body.timezone, calendar_id=calendar_id,
            start=start.replace(tzinfo=timezone.utc).isoformat(), end=end.replace(tzinfo=timezone.utc).isoformat(),
            event_id=action_id.hex, duplicate_key=duplicate_key, inbound_message_id=str(message.id), classification_id=str(classification.id))
        booking_fields = dict(integration_id=integration.id, pipeline_id=pipeline.id, inbound_message_id=message.id, classification_id=classification.id,
            calendar_id=calendar_id, title=body.title, attendees=attendees, timezone=body.timezone, start_at=start, end_at=end, duplicate_key=duplicate_key)
    goal = Goal(objective="Review and approve " + kind.replace("_", " "), brain_version_id=brain.id, created_by=ctx.user_id,
        target_inputs=[{"company_id": str(pipeline.company_id), "source_urls": []}])
    db.add(goal)
    await db.flush()
    content_hash = digest(payload)
    document = PlanDocument(objective=goal.objective, success_metrics=["Authoritative provider confirmation"], target_segment=brain.profile["icp"],
        constraints=["Exact reviewed payload", "No live provider writes enabled", "Zero paid APIs"], assumptions=[], risks=["Remote conflicts or lost acknowledgements require reconciliation"],
        steps=[PlanStep(action=kind, outcome_id=action_id, outcome_hash=content_hash, target_index=0, side_effect="external_write",
            rationale="Explicit customer request", expected_output="Persisted provider confirmation")],
        stop_conditions=["Approval revoked", "Remote version conflict", "Integration changed"], review_checkpoint="Review the exact external action and provider state")
    envelope = {"plan": document.model_dump(mode="json"), "brain_version_id": str(brain.id), "brain_hash": brain.content_hash, "targets": goal.target_inputs}
    plan = PlanVersion(goal_id=goal.id, number=1, document=envelope, content_hash=digest(envelope), author_method="reviewed_outcome")
    db.add(plan)
    await db.flush()
    action = OutcomeAction(id=action_id, integration_id=integration.id, pipeline_id=pipeline.id, mapping_id=mapping.id if mapping else None,
        plan_id=plan.id, kind=kind, request_key=body.request_key, payload=payload, content_hash=content_hash, created_by=ctx.user_id)
    db.add(action)
    await db.flush()
    if booking_fields:
        db.add(CalendarBooking(action_id=action.id, **booking_fields))
    await emit(db, None, "outcome_draft_created", {"action_id": str(action.id), "hash": content_hash, "actor": str(ctx.user_id)})
    await db.commit()
    return action


async def crm_properties(db, pipeline, object_type):
    company = await scoped_record(db, Company, pipeline.company_id)
    await db.refresh(company, with_for_update=True)
    if object_type == "company":
        return {"name": company.name, "domain": company.domain}
    if object_type == "contact":
        contact = await scoped_record(db, Contact, pipeline.contact_id)
        await db.refresh(contact, with_for_update=True)
        if contact.company_id != pipeline.company_id:
            raise HTTPException(409, "Prospect account changed")
        return {"firstname": contact.first_name, "lastname": contact.last_name, "email": address(contact.email)}
    return {"dealname": company.name + " opportunity"}


async def validate_crm_base(db, action, pipeline):
    mapping = await scoped_record(db, CRMMapping, action.mapping_id)
    await db.refresh(mapping)
    if mapping.revision != action.payload["mapping_revision"] or pipeline.revision != action.payload["pipeline_revision"]:
        raise ProviderError("remote_conflict")
    current = await crm_properties(db, pipeline, action.payload["object_type"])
    expected = action.payload["properties"]
    if action.payload["object_type"] == "opportunity":
        current.update(pipeline=expected["pipeline"], dealstage=expected["dealstage"])
    if current != expected:
        raise HTTPException(409, "Local data changed after review")


def normalize_times(start, end, zone):
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "A valid IANA timezone is required") from None
    for value in (start, end):
        if value.tzinfo is None or value.utcoffset() != value.astimezone(tz).utcoffset() or value.replace(tzinfo=None) != value.astimezone(tz).replace(tzinfo=None):
            raise HTTPException(422, "Use an explicit valid local offset for the IANA timezone; nonexistent times are rejected")
    a, b = start.astimezone(timezone.utc).replace(tzinfo=None), end.astimezone(timezone.utc).replace(tzinfo=None)
    if a <= datetime.utcnow() or b <= a or b - a > timedelta(hours=8):
        raise HTTPException(422, "Meeting must be in the future with duration at most eight hours")
    return a, b


async def intent(db, pipeline, message_id, classification_id):
    message = await scoped_record(db, InboundMessage, message_id)
    classification = await latest_classification(db, message.id)
    if not pipeline.contact_id or message.contact_id != pipeline.contact_id or message.company_id != pipeline.company_id or message.auto_submitted != "no" or not classification or classification.id != classification_id or classification.category not in {"positive", "meeting_intent"}:
        raise HTTPException(409, "Current supported positive/meeting intent for this prospect is required")
    await unsuppressed(db, message.sender_email)
    contact = await scoped_record(db, Contact, pipeline.contact_id)
    await db.refresh(contact, with_for_update=True)
    if contact.company_id != pipeline.company_id or address(contact.email) != message.sender_email:
        raise HTTPException(409, "Reply contact changed")
    return message, classification


async def validate_action(db, action, plan, spec=None):
    if action.plan_id != plan.id or digest(action.payload) != action.content_hash:
        raise HTTPException(409, "Action does not match its immutable plan")
    if spec and (spec.outcome_hash != action.content_hash or spec.action != action.kind or str(action.payload["brain_version_id"]) != plan.document["brain_version_id"] or action.payload["company_id"] != plan.document["targets"][spec.target_index]["company_id"]):
        raise HTTPException(409, "Approved action context does not match")
    return action


async def authorize_dispatch(db, command, cycle, token):
    from backend.execution_worker import approved
    await lock_workspace(db)
    await db.refresh(cycle, with_for_update=True)
    await db.refresh(command, with_for_update=True)
    plan = await approved(db, cycle)
    if command.status != "running" or command.lease_token != token or not command.lease_until or command.lease_until <= datetime.utcnow() or cycle.status != "running" or not plan:
        raise HTTPException(409, "Execution authorization changed")
    action = await scoped_record(db, OutcomeAction, UUID(command.payload["outcome_id"]))
    await db.refresh(action)
    await validate_action(db, action, plan)
    if command.payload["outcome_hash"] != action.content_hash or command.kind != action.kind:
        raise HTTPException(409, "Command payload changed")
    integration = await healthy(db, action.integration_id, action.kind)
    if await binding(db, integration) != action.payload["integration_binding"]:
        raise HTTPException(409, "Integration account/config changed; review a new action")
    return action, integration


async def execute(db, command, cycle):
    token = command.lease_token
    action, integration = await authorize_dispatch(db, command, cycle, token)
    if action.state == "confirmed":
        return output(action)
    if action.state in {"conflict", "blocked"}:
        raise HTTPException(409, "Action requires new reviewed input")
    from backend.security import decrypt_credentials
    # Disabled transports fail before any credential refresh/provider call.
    adapter = outcome_providers.adapter_for(integration, decrypt_credentials(integration.credentials))
    transport = adapter.transport
    if not transport.durable_idempotency or not transport.atomic_versions:
        action.state, action.last_error = "blocked", "live_outcomes_disabled"
        await db.commit()
        raise ProviderError("live_outcomes_disabled")
    request = adapter.encode(action.payload)
    namespace, key = str(integration.id), str(action.id)
    try:
        credentials = await integration_service.refresh_if_needed(db, integration, action.created_by)
        transport = outcome_providers.adapter_for(integration, credentials).transport
        if not transport.durable_idempotency or not transport.atomic_versions:
            raise ProviderError("live_outcomes_disabled")
        receipt = await transport.lookup(namespace, key)
        if receipt is None:
            pipeline = await scoped_record(db, PipelineRecord, action.pipeline_id)
            await db.refresh(pipeline)
            if action.kind == "crm_sync":
                await validate_crm_base(db, action, pipeline)
            else:
                await intent(db, pipeline, UUID(action.payload["inbound_message_id"]), UUID(action.payload["classification_id"]))
                for email in action.payload["attendees"]:
                    await unsuppressed(db, email)
                if datetime.fromisoformat(action.payload["start"]).replace(tzinfo=None) <= datetime.utcnow():
                    raise HTTPException(409, "Scheduling time has passed")
            action.state, action.attempted_at = "sending", datetime.utcnow()
            await db.commit()  # Persist intent before entering the provider boundary.
            action, integration = await authorize_dispatch(db, command, cycle, token)
            pipeline = await scoped_record(db, PipelineRecord, action.pipeline_id)
            await db.refresh(pipeline)
            if action.kind == "crm_sync":
                await validate_crm_base(db, action, pipeline)
            else:
                await intent(db, pipeline, UUID(action.payload["inbound_message_id"]), UUID(action.payload["classification_id"]))
                for email in action.payload["attendees"]:
                    await unsuppressed(db, email)
            # Credential renewal uses Phase 2's persisted workspace integration.
            credentials = await integration_service.refresh_if_needed(db, integration, action.created_by)
            transport = outcome_providers.adapter_for(integration, credentials).transport
            if not transport.durable_idempotency or not transport.atomic_versions:
                raise ProviderError("live_outcomes_disabled")
            if command.lease_until <= datetime.utcnow():
                raise HTTPException(409, "Dispatch lease expired during provider preparation")
            if action.kind == "calendar_schedule" and datetime.fromisoformat(action.payload["start"]).replace(tzinfo=None) <= datetime.utcnow():
                raise HTTPException(409, "Scheduling time passed during provider preparation")
            receipt = await transport.apply(namespace, key, request)
        if not isinstance(receipt, dict) or receipt.get("status") != "confirmed" or not receipt.get("id") or receipt.get("request_hash") != digest(request) or not receipt.get("version"):
            raise ProviderError("provider_not_confirmed")
        if request["external_id"] and receipt["id"] != request["external_id"]:
            raise ProviderError("provider_identity_mismatch")
        action.state, action.external_id, action.confirmed_at = "confirmed", receipt["id"], datetime.utcnow()
        action.receipt, action.last_error = receipt, None
        if action.kind == "crm_sync":
            mapping = await scoped_record(db, CRMMapping, action.mapping_id)
            # Preserve newer webhook state rather than overwrite it with an old ack.
            if mapping.revision == action.payload["mapping_revision"]:
                mapping.external_id, mapping.remote_version, mapping.remote_snapshot = receipt["id"], receipt["version"], request["properties"]
                mapping.sync_state, mapping.last_success_at, mapping.last_error = "synced", datetime.utcnow(), None
                mapping.revision += 1
            else:
                mapping.sync_state, mapping.last_error = "conflict", "newer_remote_state"
        else:
            pipeline = await scoped_record(db, PipelineRecord, action.pipeline_id)
            await pipeline_service.transition(db, pipeline, "meeting", "calendar", "calendar:" + str(action.id), "Provider confirmed scheduled event", cycle=cycle,
                evidence={"action_id": str(action.id), "provider_event_id": action.external_id, "inbound_message_id": action.payload["inbound_message_id"]})
        await emit(db, cycle, "outcome_confirmed", {"action_id": str(action.id), "provider_id": action.external_id})
        await db.commit()
        return output(action)
    except SQLAlchemyError:
        await db.rollback()
        raise  # Existing command retry reconciles a persisted provider intent.
    except Exception as error:
        code = error.code if isinstance(error, ProviderError) else "outcome_safeguard" if isinstance(error, HTTPException) else "provider_outcome_unknown"
        action.state = "conflict" if code == "remote_conflict" else "blocked" if isinstance(error, HTTPException) else "reconciling" if action.attempted_at else "failed"
        action.last_error = code
        if action.mapping_id:
            mapping = await scoped_record(db, CRMMapping, action.mapping_id)
            mapping.sync_state, mapping.last_error = action.state, code
        await emit(db, cycle, "outcome_requires_review", {"action_id": str(action.id), "reason": code})
        await db.commit()
        raise


def output(action):
    return {"outcome_id": str(action.id), "provider_object_id": action.external_id}


async def reconcile(db, action, ctx):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    await db.refresh(action)
    if action.state == "confirmed":
        return action
    cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.plan_id == action.plan_id).with_for_update())
    from backend.execution_worker import approved
    if not cycle or not await approved(db, cycle) or cycle.status == "cancelled" or action.state in {"conflict", "blocked"}:
        raise HTTPException(409, "Valid approval and reconcilable operation required")
    command = await db.scalar(select(ActionCommand).where(ActionCommand.cycle_id == cycle.id).with_for_update())
    if command.status == "running" and command.lease_until and command.lease_until > datetime.utcnow():
        raise HTTPException(409, "An active worker still owns reconciliation")
    from backend.planning_models import StepRun
    step = await scoped_record(db, StepRun, command.step_id)
    command.status, command.attempts, command.due_at = "queued", 0, datetime.utcnow()
    command.lease_token, command.lease_until, command.error_code = None, None, None
    step.status, cycle.status, cycle.stop_reason = "pending", "running", None
    await emit(db, cycle, "outcome_reconciliation_requested", {"action_id": str(action.id), "actor": str(ctx.user_id)})
    await db.commit()
    return action


class CRMEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_event_id: str = Field(min_length=1, max_length=255)
    mapping_id: UUID
    external_id: str = Field(min_length=1, max_length=255)
    remote_version: str = Field(min_length=1, max_length=255)
    properties: dict[str, str | None] = Field(max_length=30)
    cursor: str | None = Field(default=None, max_length=500)
    business_stage: Literal["opportunity", "won", "lost"] | None = None


async def receive_crm_event(db, integration_id, body):
    """Trusted authenticated adapter entry; persists observations without external writes."""
    await lock_workspace(db)
    integration = await healthy(db, integration_id, "crm_sync")
    mapping = await scoped_record(db, CRMMapping, body.mapping_id)
    if mapping.integration_id != integration.id or mapping.external_id != body.external_id:
        raise HTTPException(409, "Provider event must match a stored external mapping")
    payload = body.model_dump(mode="json")
    content_hash = digest(payload)
    previous = await db.scalar(select(CRMReceipt).where(CRMReceipt.integration_id == integration.id, CRMReceipt.provider_event_id == body.provider_event_id))
    if previous:
        if previous.content_hash != content_hash:
            raise HTTPException(409, "Provider event identity conflict")
        return previous
    row = CRMReceipt(integration_id=integration.id, mapping_id=mapping.id, provider_event_id=body.provider_event_id, content_hash=content_hash, payload=payload)
    db.add(row)
    # Never apply potentially out-of-order remote properties blindly.
    if body.remote_version != mapping.remote_version or body.properties != mapping.remote_snapshot:
        mapping.sync_state, mapping.last_error = "conflict", "remote_change_requires_review"
        mapping.revision += 1
    await emit(db, None, "crm_remote_event_received", {"mapping_id": str(mapping.id), "event_id": body.provider_event_id})
    await db.commit()
    return row


async def review_remote(db, mapping, receipt, ctx, expected_revision):
    ctx.require("owner", "admin")
    await lock_workspace(db)
    await db.refresh(mapping)
    if mapping.revision != expected_revision or receipt.mapping_id != mapping.id:
        raise HTTPException(409, "Review current mapping and matching remote evidence")
    # This accepts a snapshot as the next conditional-write base; it performs no remote write.
    # If it is stale, the provider's atomic version check still rejects the next sync.
    mapping.remote_version = receipt.payload["remote_version"]
    mapping.remote_snapshot = receipt.payload["properties"]
    mapping.cursor = receipt.payload["cursor"]
    mapping.sync_state, mapping.last_error = "reviewed_remote", None
    mapping.revision += 1
    stage = receipt.payload.get("business_stage")
    if stage:
        if mapping.object_type != "opportunity":
            raise HTTPException(409, "Only explicit opportunity data can set business outcomes")
        pipeline = await scoped_record(db, PipelineRecord, mapping.pipeline_id)
        await pipeline_service.transition(db, pipeline, stage, "reviewed_crm", "crm:" + str(receipt.id), "Administrator accepted explicit CRM outcome",
            actor=ctx.user_id, evidence={"receipt_id": str(receipt.id)}, manual=True)
    await emit(db, None, "crm_remote_reviewed", {"mapping_id": str(mapping.id), "receipt_id": str(receipt.id), "actor": str(ctx.user_id)})
    await db.commit()
    return mapping
