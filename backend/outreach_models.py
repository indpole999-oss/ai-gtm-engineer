"""Workspace-owned outreach snapshots and provider delivery state."""
from sqlalchemy import Column, Uuid, String, Text, Integer, DateTime, JSON, ForeignKey, UniqueConstraint, CheckConstraint, event, inspect
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.database import Base
from backend.planning_models import ScopedExecutionRow, parent


class Campaign(ScopedExecutionRow, Base):
    __tablename__ = "campaigns"
    name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    __table_args__ = (UniqueConstraint("workspace_id", "id"),)


class Sequence(ScopedExecutionRow, Base):
    __tablename__ = "sequences"
    campaign_id = Column(Uuid, nullable=False)
    name = Column(String(200), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), parent("campaign_id", "campaigns"))


class SequenceVersion(ScopedExecutionRow, Base):
    __tablename__ = "sequence_versions"
    sequence_id = Column(Uuid, nullable=False)
    number = Column(Integer, nullable=False)
    definition = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("sequence_id", "number"), parent("sequence_id", "sequences"))


class SequenceStep(ScopedExecutionRow, Base):
    __tablename__ = "sequence_steps"
    version_id = Column(Uuid, nullable=False)
    position = Column(Integer, nullable=False)
    delay_seconds = Column(Integer, nullable=False)
    purpose = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("version_id", "position"), parent("version_id", "sequence_versions"), CheckConstraint("delay_seconds >= 0"))


class SenderIdentity(ScopedExecutionRow, Base):
    __tablename__ = "sender_identities"
    email = Column(String(255), nullable=False)
    provider = Column(String(40), nullable=False)
    integration_id = Column(Uuid)
    status = Column(String(20), nullable=False, default="disabled")
    daily_limit = Column(Integer, nullable=False, default=20)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("workspace_id", "email"), parent("integration_id", "integrations"), CheckConstraint("daily_limit > 0 AND daily_limit <= 100"))


class Enrollment(ScopedExecutionRow, Base):
    __tablename__ = "enrollments"
    version_id = Column(Uuid, nullable=False)
    contact_id = Column(Uuid, nullable=False)
    sender_id = Column(Uuid, nullable=False)
    research_job_id = Column(Uuid, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("version_id", "contact_id"), parent("version_id", "sequence_versions"), parent("contact_id", "contacts"), parent("sender_id", "sender_identities"), parent("research_job_id", "research_jobs"))


class ScheduledMessage(ScopedExecutionRow, Base):
    __tablename__ = "scheduled_messages"
    enrollment_id = Column(Uuid, nullable=False)
    sequence_step_id = Column(Uuid, nullable=False)
    due_at = Column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("enrollment_id", "sequence_step_id"), parent("enrollment_id", "enrollments"), parent("sequence_step_id", "sequence_steps"))


class MessageDraft(ScopedExecutionRow, Base):
    __tablename__ = "message_drafts"
    scheduled_id = Column(Uuid, nullable=False)
    envelope = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), parent("scheduled_id", "scheduled_messages"))


class Message(ScopedExecutionRow, Base):
    __tablename__ = "messages"
    draft_id = Column(Uuid, nullable=False, unique=True)
    scheduled_id = Column(Uuid, nullable=False, unique=True)
    approved_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    approved_hash = Column(String(64), nullable=False)
    plan_id = Column(Uuid, nullable=False, unique=True)
    state = Column(String(30), nullable=False, default="approved")
    provider_message_id = Column(String(255))
    attempted_at = Column(DateTime)
    accepted_at = Column(DateTime)
    error_code = Column(String(80))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), parent("draft_id", "message_drafts"), parent("scheduled_id", "scheduled_messages"), parent("plan_id", "plan_versions"), CheckConstraint("state != 'sent' OR (provider_message_id IS NOT NULL AND accepted_at IS NOT NULL)"))


class DeliveryEvent(ScopedExecutionRow, Base):
    __tablename__ = "delivery_events"
    message_id = Column(Uuid, nullable=False)
    provider_event_id = Column(String(255), nullable=False)
    kind = Column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "provider_event_id"), parent("message_id", "messages"))


class Suppression(ScopedExecutionRow, Base):
    __tablename__ = "suppressions"
    email = Column(String(255), nullable=False)
    reason = Column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)


IMMUTABLE = (SequenceVersion, SequenceStep, ScheduledMessage, MessageDraft, DeliveryEvent, Suppression)
MESSAGE_APPROVAL_FIELDS = ("draft_id", "scheduled_id", "approved_by", "approved_hash", "plan_id")


@event.listens_for(Session, "before_flush")
def preserve_outreach(session, *_):
    for row in list(session.dirty) + list(session.deleted):
        if isinstance(row, IMMUTABLE):
            raise HTTPException(409, "Outreach snapshot is immutable; create a new version")
        if isinstance(row, Message) and (row in session.deleted or any(inspect(row).attrs[f].history.has_changes() for f in MESSAGE_APPROVAL_FIELDS)):
            raise HTTPException(409, "Message approval is immutable")
        if isinstance(row, Message):
            history = inspect(row).attrs.state.history
            previous = history.deleted[0] if history.deleted else row.state
            if previous == "sent":
                raise HTTPException(409, "Provider acceptance is immutable; append delivery events")
        if isinstance(row, Enrollment) and any(inspect(row).attrs[f].history.has_changes() for f in ("version_id", "contact_id", "sender_id", "research_job_id")):
            raise HTTPException(409, "Enrollment references are immutable")
