"""Versioned, workspace-owned customer knowledge. Published snapshots are immutable."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Uuid, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, event, inspect, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.database import Base, WorkspaceOwned


class CompanyBrain(WorkspaceOwned, Base):
    __tablename__ = "company_brains"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("workspace_id", "id"),)


class CompanyBrainVersion(WorkspaceOwned, Base):
    __tablename__ = "company_brain_versions"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    brain_id = Column(Uuid, nullable=False)
    number = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    profile = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=True)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    published_by = Column(Uuid, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    __mapper_args__ = {"version_id_col": revision}
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"), UniqueConstraint("brain_id", "number"),
        CheckConstraint("status IN ('draft','published')"),
        ForeignKeyConstraint(["workspace_id", "brain_id"], ["company_brains.workspace_id", "company_brains.id"]),
    )


class CompanyBrainSource(WorkspaceOwned, Base):
    __tablename__ = "company_brain_sources"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    version_id = Column(Uuid, nullable=False)
    key = Column(String(80), nullable=False)
    kind = Column(String(30), nullable=False)
    title = Column(String(300), nullable=False)
    url = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"), UniqueConstraint("version_id", "key"),
        ForeignKeyConstraint(["workspace_id", "version_id"], ["company_brain_versions.workspace_id", "company_brain_versions.id"]),
    )


class BrainClaim(WorkspaceOwned, Base):
    __tablename__ = "brain_claims"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    version_id = Column(Uuid, nullable=False)
    text = Column(Text, nullable=False)
    disposition = Column(String(20), nullable=False)
    source_key = Column(String(80), nullable=True)
    __table_args__ = (
        CheckConstraint("disposition IN ('approved','prohibited')"),
        ForeignKeyConstraint(["workspace_id", "version_id"], ["company_brain_versions.workspace_id", "company_brain_versions.id"]),
        ForeignKeyConstraint(["version_id", "source_key"], ["company_brain_sources.version_id", "company_brain_sources.key"]),
    )


@event.listens_for(Session, "before_flush")
def immutable_published_brain(session, *_):
    for row in list(session.dirty) + list(session.deleted):
        if isinstance(row, CompanyBrainVersion):
            history = inspect(row).attrs.status.history
            old = history.deleted[0] if history.deleted else row.status
            if old == "published":
                raise HTTPException(409, "Published Company Brain versions are immutable")
    for row in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(row, (CompanyBrainSource, BrainClaim)):
            parent = session.scalar(select(CompanyBrainVersion).where(CompanyBrainVersion.id == row.version_id))
            if parent is None or parent.status == "published":
                raise HTTPException(409, "Source and claim changes require a draft version")
