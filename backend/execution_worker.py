"""Database-backed worker. Run with python -m backend.execution_worker.

Trusted worker sessions bind one workspace at a time. No customer credentials
come from deployment-global provider variables. Only approved commands execute.
"""
import asyncio
from datetime import datetime, timedelta
from uuid import UUID, uuid4, uuid5
from sqlalchemy import select, update, or_, and_, func
from backend.database import AsyncSessionLocal, Workspace, WorkspaceMembership, User
from backend import tenancy  # noqa: F401; register scoping and transaction hooks
from backend.planning_models import PlanVersion, ExecutionCycle, StepRun, ActionCommand, DomainEvent, OutboxEvent
from backend.brain_models import CompanyBrainVersion
from backend.planning_service import PlanDocument, ResearchStepOutput, digest, emit, command_payload
from backend import outreach_models  # noqa: F401; standalone worker metadata
from backend import inbox_models  # noqa: F401; standalone worker metadata
from backend.research_models import ResearchJob
from backend.research_service import execute_research


def bind(db, workspace_id):
    db.info.update(workspace_id=workspace_id, workspace_role="admin")


async def approved(db, cycle):
    plan = await db.scalar(select(PlanVersion).where(PlanVersion.id == cycle.plan_id))
    if not plan or plan.status != "approved" or plan.content_hash != cycle.plan_hash or digest(plan.document) != cycle.plan_hash:
        return None
    brain = await db.scalar(select(CompanyBrainVersion).where(CompanyBrainVersion.id == UUID(plan.document["brain_version_id"])))
    if not brain or brain.status != "published" or brain.content_hash != plan.document["brain_hash"]:
        return None
    membership = await db.scalar(select(WorkspaceMembership).join(User, User.id == WorkspaceMembership.user_id).join(Workspace, Workspace.id == WorkspaceMembership.workspace_id).where(
        WorkspaceMembership.workspace_id == cycle.workspace_id, WorkspaceMembership.user_id == plan.approved_by,
        WorkspaceMembership.status == "active", WorkspaceMembership.role.in_(["owner", "admin"]), User.is_active.is_(True), Workspace.status == "active"))
    return plan if membership else None


async def admission(db, workspace_id, now):
    """Shared admission for approved actions and internal outbox consumption."""
    workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
    if not workspace or workspace.status != "active":
        return False
    commands = await db.scalar(select(func.count(ActionCommand.id)).where(ActionCommand.status == "running", ActionCommand.lease_until > now))
    events = await db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == "running", OutboxEvent.lease_until > now))
    recent = await db.scalar(select(func.count(DomainEvent.id)).where(DomainEvent.kind == "command_claimed", DomainEvent.created_at > now - timedelta(minutes=1)))
    return commands + events < 2 and recent < 10


async def claim_next(workspace_id):
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        bind(db, workspace_id)
        # Serialize admission per workspace, including across different cycles.
        # Fixed zero-paid-budget policy is deliberately conservative for Phase 5.
        if not await admission(db, workspace_id, now):
            return None
        candidates = (await db.scalars(select(ActionCommand).where(or_(
            and_(ActionCommand.status == "queued", ActionCommand.due_at <= now),
            and_(ActionCommand.status == "running", ActionCommand.lease_until <= now))).order_by(ActionCommand.created_at).limit(100))).all()
        for command in candidates:
            cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == command.cycle_id).with_for_update())
            if not cycle or cycle.status != "running":
                continue
            plan = await approved(db, cycle)
            if plan is None:
                cycle.status, cycle.stop_reason = "paused", "approval_no_longer_valid"
                await emit(db, cycle, "approval_invalidated", {})
                await db.commit()
                return None
            policy = PlanDocument.model_validate(plan.document["plan"])
            step = await db.scalar(select(StepRun).where(StepRun.id == command.step_id))
            spec = policy.steps[step.position] if step and step.position < len(policy.steps) else None
            expected = command_payload(plan, spec) if spec else None
            if not spec or command.kind != spec.action or command.payload != expected:
                cycle.status, cycle.stop_reason = "paused", "command_integrity_failed"
                await emit(db, cycle, "command_integrity_failed", {"command_id": str(command.id)})
                await db.commit()
                return None
            if command.attempts >= policy.max_attempts:
                command.status, command.error_code = "failed", "attempt_limit"
                cycle.status, cycle.stop_reason = "failed", "attempt_limit"
                await emit(db, cycle, "execution_failed", {"command_id": str(command.id), "reason": "attempt_limit"})
                await db.commit()
                return None
            dependencies = command.payload["dependencies"]
            if command.kind == "outreach_send":
                from backend.outreach_models import Message, ScheduledMessage
                message = await db.scalar(select(Message).where(Message.id == UUID(command.payload["message_id"])))
                schedule = await db.scalar(select(ScheduledMessage).where(ScheduledMessage.id == message.scheduled_id)) if message else None
                from backend.outreach_service import schedule_ready
                if not schedule or not await schedule_ready(db, schedule):
                    continue
            completed = set((await db.scalars(select(StepRun.position).where(StepRun.cycle_id == cycle.id, StepRun.status == "succeeded"))).all())
            if not set(dependencies).issubset(completed):
                continue
            token = uuid4()
            # Core CAS is deliberately isolated here; normal ORM bulk writes
            # are forbidden by tenancy.py. Conditions prevent duplicate claims.
            table = ActionCommand.__table__
            condition = and_(table.c.id == command.id, table.c.workspace_id == workspace_id, table.c.status == command.status, table.c.attempts == command.attempts)
            if command.status == "running":
                condition = and_(condition, table.c.lease_token == command.lease_token, table.c.lease_until <= now)
            else:
                condition = and_(condition, table.c.due_at <= now)
            connection = await db.connection()
            changed = await connection.execute(update(table).where(condition).values(status="running", lease_token=token,
                lease_until=now + timedelta(seconds=policy.timeout_seconds + 30), attempts=table.c.attempts + 1))
            if changed.rowcount != 1:
                await db.rollback()
                return None
            step = await db.scalar(select(StepRun).where(StepRun.id == command.step_id))
            step.status = "running"
            await emit(db, cycle, "command_claimed", {"command_id": str(command.id), "attempt": command.attempts + 1})
            result = {"id": command.id, "token": token, "kind": command.kind, "payload": command.payload,
                      "timeout": policy.timeout_seconds, "max_attempts": policy.max_attempts, "approved_by": plan.approved_by}
            await db.commit()
            return result
    return None


async def perform(workspace_id, claim):
    if claim["kind"] not in {"research", "outreach_send"}:
        raise ValueError("Unsupported command")
    async with AsyncSessionLocal() as db:
        bind(db, workspace_id)
        command = await db.scalar(select(ActionCommand).where(ActionCommand.id == claim["id"]))
        cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == command.cycle_id))
        if command.lease_token != claim["token"] or cycle.status != "running" or not await approved(db, cycle):
            raise ValueError("Command authorization changed")
        if claim["kind"] == "outreach_send":
            from backend.outreach_service import deliver
            return await deliver(db, command, cycle)
        job_id = uuid5(claim["id"], "research")
        job = await db.scalar(select(ResearchJob).where(ResearchJob.id == job_id))
        if job and job.status == "completed":
            return {"research_job_id": str(job_id)}
        if not job:
            target = claim["payload"]["target"]
            job = ResearchJob(id=job_id, company_id=UUID(target["company_id"]), brain_version_id=UUID(claim["payload"]["brain_version_id"]),
                              source_urls=target["source_urls"], created_by=claim["approved_by"])
            db.add(job)
        else:
            job.status, job.error_code = "queued", None
        await db.commit()
        await execute_research(db, job)
        return {"research_job_id": str(job_id)}


async def finish(workspace_id, claim, result=None, error=None):
    async with AsyncSessionLocal() as db:
        bind(db, workspace_id)
        command = await db.scalar(select(ActionCommand).where(ActionCommand.id == claim["id"]))
        if not command:
            return
        # Match claim/control lock order: cycle before command, avoiding a
        # completion-vs-cancellation deadlock.
        cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.id == command.cycle_id).with_for_update())
        command = await db.scalar(select(ActionCommand).where(ActionCommand.id == claim["id"]).with_for_update().execution_options(populate_existing=True))
        if not command or command.lease_token != claim["token"] or command.status != "running":
            return  # A stale worker must never acknowledge a newer worker's lease.
        if error is None:
            try:
                if command.kind == "outreach_send":
                    from backend.outreach_models import Message
                    message = await db.scalar(select(Message).where(Message.id == UUID(command.payload["message_id"])))
                    if not message or message.plan_id != cycle.plan_id or message.state != "sent" or result != {"message_id": str(message.id), "provider_message_id": message.provider_message_id}:
                        raise ValueError("Result is not this command's provider-confirmed send")
                else:
                    result = ResearchStepOutput.model_validate(result).model_dump(mode="json")
                    job = await db.scalar(select(ResearchJob).where(ResearchJob.id == UUID(result["research_job_id"])))
                    if not job or job.id != uuid5(command.id, "research") or job.status != "completed":
                        raise ValueError("Result is not this command's completed research")
            except (ValueError, TypeError):
                error = "invalid_step_output"
        step = await db.scalar(select(StepRun).where(StepRun.id == command.step_id))
        command.lease_until, command.lease_token = None, None
        if cycle.status == "cancelled":
            command.status, step.status = "cancelled", "cancelled"
        elif error:
            command.error_code = error
            if command.attempts < claim["max_attempts"]:
                command.status, step.status = "queued", "pending"
                command.due_at = datetime.utcnow() + timedelta(seconds=min(300, 2 ** command.attempts))
            else:
                command.status, step.status, cycle.status = "failed", "failed", "failed"
                cycle.stop_reason = "command_failed"
        else:
            command.status, step.status, step.output = "succeeded", "succeeded", result
        if cycle.status == "running" and not await approved(db, cycle):
            cycle.status, cycle.stop_reason = "paused", "approval_no_longer_valid"
        await db.flush()
        remaining = await db.scalar(select(StepRun.id).where(StepRun.cycle_id == cycle.id, StepRun.status != "succeeded").limit(1))
        if remaining is None and cycle.status == "running":
            cycle.status = "completed"
        await emit(db, cycle, "command_" + command.status, {"command_id": str(command.id), "error": error})
        await db.commit()


async def run_once(workspace_id):
    from backend.inbox_worker import consume_once
    if await consume_once(workspace_id):
        return True
    claim = await claim_next(workspace_id)
    if not claim:
        return False
    try:
        result = await asyncio.wait_for(perform(workspace_id, claim), timeout=claim["timeout"])
    except asyncio.CancelledError:
        raise  # Leave the lease for restart recovery; no false acknowledgement.
    except Exception:
        await finish(workspace_id, claim, error="command_execution_failed")
    else:
        await finish(workspace_id, claim, result=result)
    return True


async def main():
    while True:
        async with AsyncSessionLocal() as db:
            workspaces = (await db.scalars(select(Workspace.id).where(Workspace.status == "active"))).all()
        for workspace_id in workspaces:
            await run_once(workspace_id)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
