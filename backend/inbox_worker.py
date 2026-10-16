"""Internal inbox consumer for Phase 5's outbox, called by the existing worker.

There is no separate scheduler or worker entry point. Inbound receipt and immediate
safety effects are already durable; this consumes only deferred classification.
"""
import asyncio
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy import select, update, and_, or_
from backend.database import AsyncSessionLocal, Workspace
from backend.planning_models import OutboxEvent, DomainEvent, ExecutionCycle
from backend.planning_service import emit
from backend.outreach_service import lock_workspace
from backend.inbox_models import InboundMessage
from backend import inbox_service
from backend.research_service import scoped_record


async def claim_next(workspace_id):
    from backend.execution_worker import bind, admission
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        bind(db, workspace_id)
        if not await admission(db, workspace_id, now):
            return None
        pair = (await db.execute(select(OutboxEvent, DomainEvent).join(DomainEvent, DomainEvent.id == OutboxEvent.event_id).where(
            DomainEvent.kind == "inbound_received", or_(
                and_(OutboxEvent.status == "pending", OutboxEvent.due_at <= now),
                and_(OutboxEvent.status == "running", OutboxEvent.lease_until <= now))).order_by(OutboxEvent.created_at).limit(1))).first()
        if not pair:
            return None
        work, event = pair
        cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == event.cycle_id)) if event.cycle_id else None
        if work.attempts >= 3:
            work.status, work.error_code, work.lease_token, work.lease_until = "failed", "attempt_limit", None, None
            await emit(db, cycle, "inbound_processing_failed", {"outbox_id": str(work.id), "reason": "attempt_limit"})
            await db.commit()
            return None
        token = uuid4()
        table = OutboxEvent.__table__
        condition = and_(table.c.id == work.id, table.c.workspace_id == workspace_id, table.c.status == work.status, table.c.attempts == work.attempts)
        if work.status == "running":
            condition = and_(condition, table.c.lease_token == work.lease_token, table.c.lease_until <= now)
        connection = await db.connection()
        changed = await connection.execute(update(table).where(condition).values(status="running", attempts=table.c.attempts + 1, lease_token=token, lease_until=now + timedelta(seconds=150)))
        if changed.rowcount != 1:
            await db.rollback()
            return None
        await emit(db, cycle, "command_claimed", {"consumer": "inbox", "outbox_id": str(work.id), "attempt": work.attempts + 1})
        claim = {"id": work.id, "token": token}
        await db.commit()
        return claim


async def perform(workspace_id, claim):
    from backend.execution_worker import bind
    async with AsyncSessionLocal() as db:
        bind(db, workspace_id)
        await lock_workspace(db)
        workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id))
        work = await db.scalar(select(OutboxEvent).where(OutboxEvent.id == claim["id"]).with_for_update())
        if not workspace or workspace.status != "active" or not work or work.status != "running" or work.lease_token != claim["token"] or work.lease_until <= datetime.utcnow():
            return False
        event = await scoped_record(db, DomainEvent, work.event_id)
        if event.kind != "inbound_received":
            raise ValueError("Unexpected outbox event")
        message = await scoped_record(db, InboundMessage, UUID(event.data["inbound_message_id"]))
        await inbox_service.classify_message(db, message)
        work.status, work.delivered_at, work.error_code = "processed", datetime.utcnow(), None
        work.lease_token, work.lease_until = None, None
        await inbox_service.audit(db, message, "inbound_processing_completed")
        await db.commit()  # Classification, audit and acknowledgement are atomic.
        return True


async def fail(workspace_id, claim):
    from backend.execution_worker import bind
    async with AsyncSessionLocal() as db:
        bind(db, workspace_id)
        await lock_workspace(db)
        work = await db.scalar(select(OutboxEvent).where(OutboxEvent.id == claim["id"]).with_for_update())
        if not work or work.status != "running" or work.lease_token != claim["token"]:
            return
        work.status = "pending" if work.attempts < 3 else "failed"
        work.error_code = "inbound_processing_failed"
        work.due_at = datetime.utcnow() + timedelta(seconds=2 ** work.attempts)
        work.lease_token, work.lease_until = None, None
        event = await scoped_record(db, DomainEvent, work.event_id)
        cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == event.cycle_id)) if event.cycle_id else None
        await emit(db, cycle, "inbound_processing_" + work.status, {"outbox_id": str(work.id)})
        await db.commit()


async def consume_once(workspace_id):
    claim = await claim_next(workspace_id)
    if not claim:
        return False
    try:
        await asyncio.wait_for(perform(workspace_id, claim), timeout=120)
    except asyncio.CancelledError:
        raise
    except Exception:
        await fail(workspace_id, claim)
    return True
