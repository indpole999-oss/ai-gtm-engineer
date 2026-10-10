"""Tenant-owned research snapshots and evidence. No global knowledge cache."""
import uuid
from datetime import datetime
from sqlalchemy import Column, Uuid, String, Text, JSON, DateTime, Float, ForeignKey, ForeignKeyConstraint, UniqueConstraint
from backend.database import Base, WorkspaceOwned
from sqlalchemy import event
from sqlalchemy.orm import Session
from fastapi import HTTPException


class ResearchJob(WorkspaceOwned, Base):
    __tablename__ = "research_jobs"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    company_id = Column(Uuid, nullable=False)
    brain_version_id = Column(Uuid, nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    source_urls = Column(JSON, nullable=False)
    error_code = Column(String(80))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"]),
        ForeignKeyConstraint(["workspace_id", "brain_version_id"], ["company_brain_versions.workspace_id", "company_brain_versions.id"]))


class SourceFetch(WorkspaceOwned, Base):
    __tablename__ = "source_fetches"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    job_id = Column(Uuid, nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String(300), nullable=False)
    publisher = Column(String(255), nullable=False)
    published_at = Column(DateTime)
    retrieved_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    extractor_version = Column(String(80), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), ForeignKeyConstraint(["workspace_id", "job_id"], ["research_jobs.workspace_id", "research_jobs.id"]))


class EvidenceItem(WorkspaceOwned, Base):
    __tablename__ = "evidence_items"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    fetch_id = Column(Uuid, nullable=False)
    excerpt = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), ForeignKeyConstraint(["workspace_id", "fetch_id"], ["source_fetches.workspace_id", "source_fetches.id"]))


class ResearchClaim(WorkspaceOwned, Base):
    __tablename__ = "research_claims"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    job_id = Column(Uuid, nullable=False)
    evidence_id = Column(Uuid)
    text = Column(Text, nullable=False)
    kind = Column(String(30), nullable=False)
    confidence = Column(Float, nullable=False)
    model_version = Column(String(100), nullable=False)
    verified_by = Column(Uuid, ForeignKey("users.id"))
    verified_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(["workspace_id", "job_id"], ["research_jobs.workspace_id", "research_jobs.id"]),
        ForeignKeyConstraint(["workspace_id", "evidence_id"], ["evidence_items.workspace_id", "evidence_items.id"]))


class AccountIntelligence(WorkspaceOwned, Base):
    __tablename__ = "account_intelligence_reports"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    job_id = Column(Uuid, nullable=False, unique=True)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (ForeignKeyConstraint(["workspace_id", "job_id"], ["research_jobs.workspace_id", "research_jobs.id"]),)


class ClaimVerification(WorkspaceOwned, Base):
    __tablename__ = "claim_verifications"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    claim_id = Column(Uuid, nullable=False)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    decision = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (ForeignKeyConstraint(["workspace_id", "claim_id"], ["research_claims.workspace_id", "research_claims.id"]),)


@event.listens_for(Session, "before_flush")
def preserve_research_evidence(session, *_):
    for row in list(session.dirty) + list(session.deleted):
        if isinstance(row, (SourceFetch, EvidenceItem, ResearchClaim, AccountIntelligence, ClaimVerification)):
            raise HTTPException(409, "Research evidence is immutable; create a new research job")
