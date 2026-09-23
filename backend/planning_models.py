"""Durable plans, approvals, execution state and transactional audit/outbox."""
import uuid
from datetime import datetime
from sqlalchemy import Column, Uuid, String, Text, JSON, Integer, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, event, inspect
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.database import Base, WorkspaceOwned


class ScopedExecutionRow(WorkspaceOwned):
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def parent(column, table):
    return ForeignKeyConstraint(["workspace_id", column], [table + ".workspace_id", table + ".id"])


class Goal(ScopedExecutionRow, Base):
    __tablename__ = "goals"
    objective = Column(Text, nullable=False)
    brain_version_id = Column(Uuid, nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)
    target_inputs = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), parent("brain_version_id", "company_brain_versions"))


class PlanVersion(ScopedExecutionRow, Base):
    __tablename__ = "plan_versions"
    goal_id = Column(Uuid, nullable=False)
    number = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    document = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    author_method = Column(String(100), nullable=False)
    approved_by = Column(Uuid, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    __mapper_args__ = {"version_id_col": revision}
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("goal_id", "number"), parent("goal_id", "goals"))


class ExecutionCycle(ScopedExecutionRow, Base):
    __tablename__ = "execution_cycles"
    plan_id = Column(Uuid, nullable=False, unique=True)
    plan_hash = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default="running")
    stop_reason = Column(String(100))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), parent("plan_id", "plan_versions"))


class StepRun(ScopedExecutionRow, Base):
    __tablename__ = "step_runs"
    cycle_id = Column(Uuid, nullable=False)
    position = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    output = Column(JSON)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("cycle_id", "position"), parent("cycle_id", "execution_cycles"))


class ActionCommand(ScopedExecutionRow, Base):
    __tablename__ = "action_commands"
    step_id = Column(Uuid, nullable=False, unique=True)
    cycle_id = Column(Uuid, nullable=False)
    kind = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    idempotency_key = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    due_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    lease_token = Column(Uuid)
    lease_until = Column(DateTime)
    error_code = Column(String(100))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("workspace_id", "idempotency_key"),
                     parent("step_id", "step_runs"), parent("cycle_id", "execution_cycles"))


class DomainEvent(ScopedExecutionRow, Base):
    __tablename__ = "domain_events"
    cycle_id = Column(Uuid, nullable=False)
    kind = Column(String(80), nullable=False)
    data = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"), parent("cycle_id", "execution_cycles"))


class OutboxEvent(ScopedExecutionRow, Base):
    __tablename__ = "outbox_events"
    event_id = Column(Uuid, nullable=False, unique=True)
    status = Column(String(30), nullable=False, default="pending")
    delivered_at = Column(DateTime)
    __table_args__ = (parent("event_id", "domain_events"),)


@event.listens_for(Session, "before_flush")
def immutable_approved_plan(session, *_):
    for row in list(session.dirty) + list(session.deleted):
        if isinstance(row, PlanVersion):
            history = inspect(row).attrs.status.history
            previous = history.deleted[0] if history.deleted else row.status
            if previous == "approved":
                raise HTTPException(409, "Approved plans are immutable")
        if isinstance(row, DomainEvent):
            raise HTTPException(409, "Execution audit is immutable")
