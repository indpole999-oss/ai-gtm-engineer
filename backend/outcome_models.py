"""Phase 8 pipeline evidence and provider operations owned by existing commands."""
from sqlalchemy import Column, Uuid, String, Text, Integer, JSON, DateTime, Boolean, ForeignKey, UniqueConstraint, CheckConstraint, Index, event, inspect
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.database import Base
from backend.planning_models import ScopedExecutionRow, parent

STAGES = ("discovered", "qualified", "contacted", "engaged", "interested", "meeting", "opportunity", "won", "lost")


class PipelineRecord(ScopedExecutionRow, Base):
    __tablename__ = "pipeline_records"
    company_id = Column(Uuid, nullable=False)
    contact_id = Column(Uuid)
    record_key = Column(String(80), nullable=False)
    stage = Column(String(30), nullable=False, default="discovered")
    revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("workspace_id", "record_key"),
        parent("company_id", "companies"), parent("contact_id", "contacts"),
        CheckConstraint("stage IN (" + ",".join(repr(s) for s in STAGES) + ")"))


class PipelineHistory(ScopedExecutionRow, Base):
    __tablename__ = "pipeline_history"
    pipeline_id = Column(Uuid, nullable=False)
    source_key = Column(String(255), nullable=False)
    from_stage = Column(String(30))
    to_stage = Column(String(30), nullable=False)
    applied = Column(Boolean, nullable=False, default=True)
    source = Column(String(40), nullable=False)
    reason = Column(Text, nullable=False)
    actor_id = Column(Uuid, ForeignKey("users.id"))
    evidence = Column(JSON, nullable=False, default=dict)
    cycle_id = Column(Uuid)
    campaign_id = Column(Uuid)
    sequence_version_id = Column(Uuid)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("pipeline_id", "source_key"),
        parent("pipeline_id", "pipeline_records"), parent("cycle_id", "execution_cycles"),
        parent("campaign_id", "campaigns"), parent("sequence_version_id", "sequence_versions"),
        Index("ix_pipeline_history_time", "workspace_id", "pipeline_id", "created_at"))


class CRMMapping(ScopedExecutionRow, Base):
    __tablename__ = "crm_mappings"
    integration_id = Column(Uuid, nullable=False)
    pipeline_id = Column(Uuid, nullable=False)
    object_type = Column(String(30), nullable=False)
    provider = Column(String(30), nullable=False)
    external_id = Column(String(255))
    remote_version = Column(String(255))
    remote_snapshot = Column(JSON)
    revision = Column(Integer, nullable=False, default=1)
    sync_state = Column(String(30), nullable=False, default="unmapped")
    last_success_at = Column(DateTime)
    last_error = Column(String(100))
    cursor = Column(String(500))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("integration_id", "pipeline_id", "object_type"),
        UniqueConstraint("integration_id", "object_type", "external_id"), parent("integration_id", "integrations"), parent("pipeline_id", "pipeline_records"),
        CheckConstraint("object_type IN ('company','contact','opportunity')"))


class OutcomeAction(ScopedExecutionRow, Base):
    __tablename__ = "outcome_actions"
    integration_id = Column(Uuid, nullable=False)
    pipeline_id = Column(Uuid, nullable=False)
    mapping_id = Column(Uuid)
    plan_id = Column(Uuid, nullable=False, unique=True)
    kind = Column(String(30), nullable=False)
    request_key = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    state = Column(String(30), nullable=False, default="draft")
    attempted_at = Column(DateTime)
    confirmed_at = Column(DateTime)
    external_id = Column(String(255))
    receipt = Column(JSON)
    last_error = Column(String(100))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("workspace_id", "request_key"),
        parent("integration_id", "integrations"), parent("pipeline_id", "pipeline_records"), parent("mapping_id", "crm_mappings"),
        parent("plan_id", "plan_versions"), CheckConstraint("kind IN ('crm_sync','calendar_schedule')"))


class CalendarBooking(ScopedExecutionRow, Base):
    __tablename__ = "calendar_bookings"
    action_id = Column(Uuid, nullable=False, unique=True)
    integration_id = Column(Uuid, nullable=False)
    pipeline_id = Column(Uuid, nullable=False)
    inbound_message_id = Column(Uuid, nullable=False)
    classification_id = Column(Uuid, nullable=False)
    calendar_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    attendees = Column(JSON, nullable=False)
    timezone = Column(String(100), nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    duplicate_key = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("workspace_id", "duplicate_key"),
        parent("action_id", "outcome_actions"), parent("integration_id", "integrations"), parent("pipeline_id", "pipeline_records"),
        parent("inbound_message_id", "inbound_messages"), parent("classification_id", "reply_classifications"),
        CheckConstraint("end_at > start_at"), Index("ix_calendar_time", "workspace_id", "start_at", "end_at"))


class CRMReceipt(ScopedExecutionRow, Base):
    __tablename__ = "crm_receipts"
    integration_id = Column(Uuid, nullable=False)
    mapping_id = Column(Uuid, nullable=False)
    provider_event_id = Column(String(255), nullable=False)
    content_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("integration_id", "provider_event_id"),
        parent("integration_id", "integrations"), parent("mapping_id", "crm_mappings"))


MODELS = (PipelineRecord, PipelineHistory, CRMMapping, OutcomeAction, CalendarBooking, CRMReceipt)
IMMUTABLE = (PipelineHistory, CalendarBooking, CRMReceipt)
PROTECTED = {PipelineRecord: ("company_id", "contact_id", "record_key"),
    CRMMapping: ("integration_id", "pipeline_id", "object_type", "provider"),
    OutcomeAction: ("integration_id", "pipeline_id", "mapping_id", "plan_id", "kind", "request_key", "payload", "content_hash", "created_by")}


@event.listens_for(Session, "before_flush")
def protect_outcome_evidence(session, *_):
    for row in list(session.dirty) + list(session.deleted):
        if isinstance(row, IMMUTABLE) or (row in session.deleted and isinstance(row, MODELS)):
            raise HTTPException(409, "Outcome history must be preserved")
        for model, fields in PROTECTED.items():
            if isinstance(row, model) and any(inspect(row).attrs[f].history.has_changes() for f in fields):
                raise HTTPException(409, "Outcome identity and approved payload are immutable")
        if isinstance(row, OutcomeAction):
            history = inspect(row).attrs.state.history
            previous = history.deleted[0] if history.deleted else row.state
            if previous == "confirmed":
                raise HTTPException(409, "Confirmed provider outcome is immutable")
        if isinstance(row, CRMMapping):
            history = inspect(row).attrs.external_id.history
            if history.has_changes() and history.deleted and history.deleted[0] is not None:
                raise HTTPException(409, "Stored external identity cannot be replaced")
