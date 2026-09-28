"""Read-only, tenant-scoped operational inventory from canonical execution state."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from backend.tenancy import get_workspace_db, get_current_workspace
from backend.planning_models import ExecutionCycle, ActionCommand, OutboxEvent, PlanVersion

router = APIRouter()


@router.get("/operations")
async def operations(ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    async def counts(model):
        rows = await db.execute(select(model.status, func.count(model.id)).group_by(model.status))
        return dict(rows.all())
    now = datetime.utcnow()
    stale = await db.scalar(select(func.count(ActionCommand.id)).where(ActionCommand.status == "running", ActionCommand.lease_until < now))
    oldest = await db.scalar(select(func.min(ActionCommand.created_at)).where(ActionCommand.status == "queued"))
    return {
        "as_of": now.isoformat() + "Z", "workspace_id": str(ctx.workspace_id),
        "cycles": await counts(ExecutionCycle), "commands": await counts(ActionCommand),
        "outbox": await counts(OutboxEvent), "plans": await counts(PlanVersion),
        "expired_command_leases": stale,
        "oldest_queued_age_seconds": max(0, (now - oldest).total_seconds()) if oldest else None,
        "provider_cost": {"status": "unavailable", "amount": None, "reason": "No authoritative billing ledger is configured"},
    }
