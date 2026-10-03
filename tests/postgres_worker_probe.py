"""Invoked only inside the disposable PostgreSQL integration test database."""
import asyncio
import sys
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from backend.database import AsyncSessionLocal, engine
from backend.planning_models import Goal
from backend.planning_service import PlanDocument, PlanStep, save_plan, approve_plan
from backend.tenancy import WorkspaceContext
from backend import execution_worker as worker


async def check():
    wid, company_id, brain_id, user_id = [UUID(value) for value in sys.argv[1:5]]
    async with AsyncSessionLocal() as db:
        worker.bind(db, wid)
        goal = Goal(objective="Concurrent research worker test", brain_version_id=brain_id, created_by=user_id,
                    target_inputs=[{"company_id": str(company_id), "source_urls": ["https://example.com/"]}])
        db.add(goal)
        await db.flush()
        document = PlanDocument(objective=goal.objective, target_segment="Test ICP", success_metrics=["One report"],
            constraints=["No paid calls"], assumptions=[], risks=["Test only"], steps=[PlanStep(action="research", target_index=0, rationale="Test", expected_output="Report")],
            stop_conditions=["Approval revoked"], review_checkpoint="Review evidence")
        plan = await save_plan(db, goal, document, "test")
        await approve_plan(db, plan, WorkspaceContext(wid, user_id, "owner"), plan.content_hash)
        try:
            connection = await db.connection()
            await connection.execute(text("UPDATE plan_versions SET content_hash='tampered' WHERE id=:id"), {"id": plan.id})
        except DBAPIError as error:
            assert "immutable" in str(error)
            await db.rollback()
        else:
            raise AssertionError("Approved plan SQL mutation was accepted")
    claims = await asyncio.gather(worker.claim_next(wid), worker.claim_next(wid))
    assert sum(claim is not None for claim in claims) == 1, "Two workers claimed the same command"
    await engine.dispose()


asyncio.run(check())
