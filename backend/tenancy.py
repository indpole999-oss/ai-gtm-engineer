"""Fail-closed workspace resolution and database enforcement.

Only authenticated dependencies or trusted workers may bind a session. Customer
tables are invisible on unbound sessions; raw/bulk SQL is not a customer API.
"""
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import event, inspect, select, text
from sqlalchemy.orm import Session, with_loader_criteria

from backend.database import (
    Company, Contact, CRMRecord, EmailLog, Meeting, Integration,
    Workspace, WorkspaceMembership, WorkspaceOwned, get_db,
)
from backend.routers.auth import get_current_user

CUSTOMER_MODELS = (Company, Contact, CRMRecord, EmailLog, Meeting, Integration)
RELATIONS = {Contact: ("company_id", Company), CRMRecord: ("contact_id", Contact),
             EmailLog: ("contact_id", Contact), Meeting: ("contact_id", Contact)}
ROLES = {"owner", "admin", "member", "viewer"}


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: UUID
    user_id: UUID
    role: str

    def require(self, *roles):
        if self.role not in roles:
            raise HTTPException(403, "Insufficient workspace permissions")


async def get_current_workspace(
    user=Depends(get_current_user), db=Depends(get_db),
    workspace_header: str | None = Header(None, alias="X-Workspace-ID"),
):
    query = select(WorkspaceMembership).join(Workspace).where(
        WorkspaceMembership.user_id == user.id,
        WorkspaceMembership.status == "active", Workspace.status == "active",
    )
    if workspace_header:
        try:
            workspace_id = UUID(workspace_header)
        except ValueError:
            raise HTTPException(400, "Invalid workspace ID")
        query = query.where(WorkspaceMembership.workspace_id == workspace_id)
    memberships = (await db.execute(query)).scalars().all()
    if not memberships:
        raise HTTPException(403, "No active workspace membership")
    if len(memberships) != 1:
        raise HTTPException(400, "Select a workspace using X-Workspace-ID")
    membership = memberships[0]
    if membership.role not in ROLES:
        raise HTTPException(403, "Invalid workspace role")
    return WorkspaceContext(membership.workspace_id, user.id, membership.role)


async def get_workspace_db(request: Request, ctx=Depends(get_current_workspace), db=Depends(get_db)):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        ctx.require("owner", "admin", "member")
        if request.method == "DELETE":
            ctx.require("owner", "admin")
        if "/integrations" in request.url.path:
            ctx.require("owner", "admin")
    previous = db.info.get("workspace_id")
    if previous and previous != ctx.workspace_id:
        raise HTTPException(403, "Cannot change workspace within a session")
    db.info.update(workspace_id=ctx.workspace_id, workspace_role=ctx.role)
    # Auth may already have opened the transaction before this dependency ran.
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT set_config('app.workspace_id', :workspace, true)"),
                         {"workspace": str(ctx.workspace_id)})
    return db


@event.listens_for(Session, "after_begin")
def set_transaction_workspace(session, transaction, connection):
    if connection.dialect.name == "postgresql" and session.info.get("workspace_id"):
        connection.execute(text("SELECT set_config('app.workspace_id', :workspace, true)"),
                           {"workspace": str(session.info["workspace_id"])})


@event.listens_for(Session, "do_orm_execute")
def scope_customer_queries(state):
    if state.is_select:
        workspace_id = state.session.info.get("workspace_id")
        # A zero UUID cannot be a valid generated workspace. NULL legacy rows
        # never match, including on sessions used by old agents/workers.
        workspace_id = workspace_id or UUID(int=0)
        state.statement = state.statement.options(with_loader_criteria(
            WorkspaceOwned, lambda model: model.workspace_id == workspace_id,
            include_aliases=True,
        ))
    elif state.is_update or state.is_delete or state.is_insert:
        raise HTTPException(403, "Bulk mutations require a reviewed service")


@event.listens_for(Session, "before_flush")
def validate_customer_writes(session, flush_context, instances):
    workspace_id = session.info.get("workspace_id")
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if not isinstance(obj, WorkspaceOwned):
            continue
        if not workspace_id:
            raise HTTPException(403, "Workspace required")
        role = session.info.get("workspace_role")
        if role not in {"owner", "admin", "member"}:
            raise HTTPException(403, "Workspace is read-only")
        if isinstance(obj, Integration) and role not in {"owner", "admin"}:
            raise HTTPException(403, "Integration administration requires admin")
        if obj in session.new and obj.workspace_id is None:
            obj.workspace_id = workspace_id
        if obj.workspace_id != workspace_id:
            raise HTTPException(404, "Record not found")
        if obj not in session.new and inspect(obj).attrs.workspace_id.history.has_changes():
            raise HTTPException(403, "Record ownership is immutable")
        relation = RELATIONS.get(type(obj))
        if relation and obj not in session.deleted:
            field, parent = relation
            parent_id = getattr(obj, field)
            if parent_id and session.scalar(select(parent.id).where(
                parent.id == parent_id, parent.workspace_id == workspace_id,
            )) is None:
                raise HTTPException(404, "Related record not found")


async def require_workspace(request: Request, db=Depends(get_workspace_db)):
    """Router-level guard covers routes without an explicit database dependency."""
    return db


async def require_approved_execution():
    raise HTTPException(409, "This legacy action requires the V2 approval and execution service")
