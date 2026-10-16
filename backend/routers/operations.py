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
    outbox_stale = await db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == "running", OutboxEvent.lease_until < now))
    approval_oldest = await db.scalar(select(func.min(PlanVersion.created_at)).where(PlanVersion.status == "draft"))
    command_counts, outbox_counts = await counts(ActionCommand), await counts(OutboxEvent)
    alerts = []
    if stale or outbox_stale:
        alerts.append("expired_leases")
    if command_counts.get("failed", 0) or outbox_counts.get("failed", 0):
        alerts.append("failed_execution")
    if oldest and (now - oldest).total_seconds() > 300:
        alerts.append("queue_wait_exceeds_5_minutes")
    return {
        "as_of": now.isoformat() + "Z", "workspace_id": str(ctx.workspace_id),
        "cycles": await counts(ExecutionCycle), "commands": command_counts,
        "outbox": outbox_counts, "plans": await counts(PlanVersion),
        "expired_command_leases": stale,
        "expired_outbox_leases": outbox_stale, "alerts": alerts,
        "oldest_pending_approval_age_seconds": max(0, (now - approval_oldest).total_seconds()) if approval_oldest else None,
        "worker_liveness": "not_measured",
        "oldest_queued_age_seconds": max(0, (now - oldest).total_seconds()) if oldest else None,
        "provider_cost": {"status": "unavailable", "amount": None, "reason": "No authoritative billing ledger is configured"},
    }


@router.get("/retention")
async def retention(ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    """Inventory only: unapproved retention periods never authorize deletion."""
    ctx.require("owner", "admin")
    from backend.research_models import SourceFetch
    from backend.inbox_models import InboundMessage
    from backend.planning_models import DomainEvent
    from backend.outreach_models import Suppression
    counts = {}
    for name, model in (("customer_evidence", SourceFetch), ("inbox_content", InboundMessage),
                        ("execution_audit", DomainEvent), ("suppression", Suppression)):
        counts[name] = {"records": await db.scalar(select(func.count(model.id))), "retention_days": None}
    return {"workspace_id": str(ctx.workspace_id), "policy_status": "approval_required",
            "automatic_purge_enabled": False, "datasets": counts,
            "backups": {"retention_days": None, "inventory": "operator_managed_unknown"},
            "deletion": "Blocked when evidence, audit or relationship integrity would be broken"}
