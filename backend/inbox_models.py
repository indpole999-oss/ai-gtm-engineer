"""Immutable inbound evidence, classifications and draft-only suggestions."""
from sqlalchemy import Column, Uuid, String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint, CheckConstraint, Index, event
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.database import Base
from backend.planning_models import ScopedExecutionRow, parent

CATEGORIES = ("positive", "negative", "objection", "out_of_office", "wrong_person", "question", "meeting_intent", "unsubscribe", "other")


class InboxThread(ScopedExecutionRow, Base):
    __tablename__ = "inbox_threads"
    sender_id = Column(Uuid, nullable=False)
    provider_thread_id = Column(String(255))
    thread_key = Column(String(300), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("sender_id", "thread_key"), parent("sender_id", "sender_identities"))


class InboundMessage(ScopedExecutionRow, Base):
    __tablename__ = "inbound_messages"
    thread_id = Column(Uuid, nullable=False)
    sender_id = Column(Uuid, nullable=False)
    provider_message_id = Column(String(255), nullable=False)
    in_reply_to = Column(String(255))
    sender_email = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    auto_submitted = Column(String(20), nullable=False)
    received_at = Column(DateTime, nullable=False)
    content_hash = Column(String(64), nullable=False)
    association = Column(String(30), nullable=False)
    outbound_message_id = Column(Uuid)
    contact_id = Column(Uuid)
    company_id = Column(Uuid)
    campaign_id = Column(Uuid)
    sequence_id = Column(Uuid)
    sequence_version_id = Column(Uuid)
    enrollment_id = Column(Uuid)
    brain_version_id = Column(Uuid)
    research_job_id = Column(Uuid)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("sender_id", "provider_message_id"),
        parent("thread_id", "inbox_threads"), parent("sender_id", "sender_identities"), parent("outbound_message_id", "messages"),
        parent("contact_id", "contacts"), parent("company_id", "companies"), parent("campaign_id", "campaigns"),
        parent("sequence_id", "sequences"), parent("sequence_version_id", "sequence_versions"), parent("enrollment_id", "enrollments"),
        parent("brain_version_id", "company_brain_versions"), parent("research_job_id", "research_jobs"),
        Index("ix_inbound_thread_received", "workspace_id", "thread_id", "received_at"))


class InboundReceipt(ScopedExecutionRow, Base):
    __tablename__ = "inbound_receipts"
    sender_id = Column(Uuid, nullable=False)
    provider_event_id = Column(String(255), nullable=False)
    content_hash = Column(String(64), nullable=False)
    inbound_message_id = Column(Uuid, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("sender_id", "provider_event_id"),
        parent("sender_id", "sender_identities"), parent("inbound_message_id", "inbound_messages"))


class InboxThreadLink(ScopedExecutionRow, Base):
    __tablename__ = "inbox_thread_links"
    thread_id = Column(Uuid, nullable=False)
    outbound_message_id = Column(Uuid, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("thread_id", "outbound_message_id"), parent("thread_id", "inbox_threads"), parent("outbound_message_id", "messages"))


class ReplyClassification(ScopedExecutionRow, Base):
    __tablename__ = "reply_classifications"
    inbound_message_id = Column(Uuid, nullable=False)
    number = Column(Integer, nullable=False)
    category = Column(String(30), nullable=False)
    confidence = Column(Float)
    reason = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False)
    classifier_version = Column(String(80), nullable=False)
    recommended_action = Column(String(80), nullable=False)
    requires_review = Column(Boolean, nullable=False)
    manual_override = Column(Boolean, nullable=False, default=False)
    overridden_by = Column(Uuid, ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("inbound_message_id", "number"),
        parent("inbound_message_id", "inbound_messages"), CheckConstraint("category IN (" + ",".join(repr(c) for c in CATEGORIES) + ")"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"))


class InboxPause(ScopedExecutionRow, Base):
    __tablename__ = "inbox_pauses"
    inbound_message_id = Column(Uuid, nullable=False)
    enrollment_id = Column(Uuid, nullable=False)
    reason = Column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("enrollment_id", "inbound_message_id"),
        parent("inbound_message_id", "inbound_messages"), parent("enrollment_id", "enrollments"))


class SuggestedReplyDraft(ScopedExecutionRow, Base):
    __tablename__ = "suggested_reply_drafts"
    inbound_message_id = Column(Uuid, nullable=False)
    classification_id = Column(Uuid, nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    context = Column(JSON, nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("inbound_message_id", "classification_id"),
        parent("inbound_message_id", "inbound_messages"), parent("classification_id", "reply_classifications"))


MODELS = (InboxThread, InboundMessage, InboundReceipt, InboxThreadLink, ReplyClassification, InboxPause, SuggestedReplyDraft)


@event.listens_for(Session, "before_flush")
def immutable_inbox(session, *_):
    if any(isinstance(row, MODELS) for row in list(session.dirty) + list(session.deleted)):
        raise HTTPException(409, "Inbox evidence and decisions are immutable; append a reviewed override")
