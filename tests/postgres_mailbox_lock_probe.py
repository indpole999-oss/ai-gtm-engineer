"""Child process: real PostgreSQL locks using application locking entry points.

The parent creates a uniquely named disposable database and migrates it. No
provider HTTP is executed. The old ordering must produce SQLSTATE 40P01, then
the fixed entry point must block on Workspace (not Integration) and complete.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from fastapi import HTTPException
from backend.main import app  # noqa: F401 -- register all models and tenant guards
from backend.database import engine, AsyncSessionLocal, Workspace, User, Integration
from backend.integration_service import connection
from backend.outreach_service import lock_workspace


async def main():
    wid, other, uid, iid = [uuid4() for _ in range(4)]
    async with engine.begin() as db:
        await db.execute(User.__table__.insert().values(id=uid, email="locks@example.com", hashed_password="synthetic", is_active=True))
        for key in (wid, other):
            await db.execute(Workspace.__table__.insert().values(id=key, name="Locks", slug=str(key), status="active"))
        await db.execute(Integration.__table__.insert().values(id=iid, workspace_id=wid, user_id=uid,
            category="email", provider="resend", auth_type="api_key", credentials={}, config={}))

    first, second = asyncio.Event(), asyncio.Event()
    async def old_order(worker):
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=wid, workspace_role="owner")
            try:
                await db.execute(text("SET LOCAL statement_timeout = '15s'"))
                if worker:
                    await lock_workspace(db)
                    first.set()
                    await second.wait()
                    await db.scalar(select(Integration).where(Integration.id == iid).with_for_update())
                else:
                    await db.scalar(select(Integration).where(Integration.id == iid).with_for_update())
                    second.set()
                    await first.wait()
                    await lock_workspace(db)
            finally:
                await db.rollback()
    results = await asyncio.wait_for(asyncio.gather(old_order(True), old_order(False), return_exceptions=True), 20)
    assert any(isinstance(error, DBAPIError) and getattr(error.orig, "sqlstate", None) == "40P01" for error in results), "Original ordering did not reproduce PostgreSQL deadlock"
    assert all(error is None or (isinstance(error, DBAPIError) and getattr(error.orig, "sqlstate", None) == "40P01") for error in results)

    # Exercise the shared integration entry point used by webhook ingestion,
    # receipt reconciliation, CRM management and transport selection.
    for receipt in (False, True):
        held, waiting, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        callback_pid = []
        async def worker():
            async with AsyncSessionLocal() as db:
                db.info.update(workspace_id=wid, workspace_role="owner")
                await lock_workspace(db)
                held.set()
                await release.wait()
                await connection(db, iid, lock=True)
                await db.commit()
        async def callback():
            await held.wait()
            async with AsyncSessionLocal() as db:
                db.info.update(workspace_id=wid, workspace_role="owner")
                callback_pid.append(await db.scalar(text("SELECT pg_backend_pid()")))
                waiting.set()
                await connection(db, iid, lock=True)
                # Both ingest() and reconcile_receipt() re-enter this lock.
                await lock_workspace(db)
                if receipt:
                    await db.commit()
                else:
                    await db.rollback()
        tasks = [asyncio.create_task(worker()), asyncio.create_task(callback())]
        try:
            await asyncio.wait_for(waiting.wait(), 10)
            async with engine.connect() as observer:
                for _ in range(100):
                    await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                    row = (await observer.execute(text("SELECT wait_event_type,query FROM pg_stat_activity WHERE pid=:pid"), {"pid": callback_pid[0]})).first()
                    if row and row[0] == "Lock":
                        assert "workspaces" in row[1], "Callback acquired a child lock before workspace"
                        break
                    await asyncio.sleep(.05)
                else:
                    raise AssertionError("Callback never waited on workspace")
            # An unrelated workspace can acquire its lock while this one waits.
            async with AsyncSessionLocal() as isolated:
                isolated.info.update(workspace_id=other, workspace_role="owner")
                await asyncio.wait_for(lock_workspace(isolated), 2)
                try:
                    await connection(isolated, iid, lock=True)
                except HTTPException as error:
                    assert error.status_code == 404
                else:
                    raise AssertionError("Cross-workspace integration exposed")
                await isolated.rollback()
            release.set()
            await asyncio.wait_for(asyncio.gather(*tasks), 10)
        finally:
            release.set()
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
