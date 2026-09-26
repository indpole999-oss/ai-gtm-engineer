"""Workspace discovery and membership administration."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
from sqlalchemy import select, func
from backend.database import Workspace, WorkspaceMembership, User, get_db
from backend.routers.auth import get_current_user
from backend.tenancy import get_current_workspace

router = APIRouter()


@router.get("")
async def my_workspaces(user=Depends(get_current_user), db=Depends(get_db)):
    rows = (await db.execute(select(Workspace, WorkspaceMembership).join(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user.id, WorkspaceMembership.status == "active",
        Workspace.status == "active",
    ))).all()
    return [{"id": w.id, "name": w.name, "slug": w.slug, "status": w.status, "role": m.role} for w, m in rows]


@router.get("/current/memberships")
async def memberships(ctx=Depends(get_current_workspace), db=Depends(get_db)):
    ctx.require("owner", "admin")
    return (await db.execute(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == ctx.workspace_id))).scalars().all()


class MembershipChange(BaseModel):
    user_id: UUID
    role: Literal["owner", "admin", "member", "viewer"]
    status: Literal["active", "suspended"] = "active"


@router.put("/current/memberships")
async def change_membership(payload: MembershipChange, ctx=Depends(get_current_workspace), db=Depends(get_db)):
    # Only owners can change access. Lock workspace to serialize last-owner checks.
    ctx.require("owner")
    await db.execute(select(Workspace).where(Workspace.id == ctx.workspace_id).with_for_update())
    user = await db.get(User, payload.user_id)
    if user is None or not user.is_active:
        raise HTTPException(404, "Active user not found")
    membership = await db.get(WorkspaceMembership, (ctx.workspace_id, payload.user_id))
    if membership and membership.role == "owner" and membership.status == "active":
        count = await db.scalar(select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == ctx.workspace_id,
            WorkspaceMembership.role == "owner", WorkspaceMembership.status == "active"))
        if count <= 1 and (payload.role != "owner" or payload.status != "active"):
            raise HTTPException(409, "Workspace must retain an active owner")
    if membership is None:
        membership = WorkspaceMembership(workspace_id=ctx.workspace_id, user_id=payload.user_id)
        db.add(membership)
    membership.role, membership.status = payload.role, payload.status
    await db.flush()
    return {"user_id": membership.user_id, "role": membership.role, "status": membership.status}
