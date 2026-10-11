"""Actual PostgreSQL cancellation/dispatch races; providers remain deterministic."""
import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from backend.main import app
from backend.database import engine, AsyncSessionLocal
from backend.config import settings
from backend import outreach_service, execution_worker, providers
from test_message_replacement import (prepared, rotate, replacement,
    test_replacement_preserves_history_requires_fresh_approval_and_deduplicates,
    test_attempted_delivery_cannot_be_replaced_after_timeout_disconnect_or_retry,
    test_disconnected_and_suppressed_replacement_is_atomic,
    test_replacement_rolls_back_when_new_draft_cannot_be_composed,
    test_replacement_requires_owner_or_admin)
from test_live_integration_boundaries import boundaries
from test_research import fake_research
from test_outreach import approve_draft, get_message
from test_planning_execution import approve


def run():
    with TestClient(app) as client:
        for scenario in ["lifecycle", "provider_timeout", "reconnect_required", "rate_limited", "suppression", "atomicity", "authorization"]:
            with pytest.MonkeyPatch.context() as patch:
                research, state = fake_research.__wrapped__(patch), boundaries.__wrapped__(patch)
                if scenario == "lifecycle":
                    test_replacement_preserves_history_requires_fresh_approval_and_deduplicates(client, research, state, patch)
                elif scenario == "atomicity":
                    test_replacement_rolls_back_when_new_draft_cannot_be_composed(client, research, state, patch)
                elif scenario == "authorization":
                    test_replacement_requires_owner_or_admin(client, research, state)
                elif scenario == "suppression":
                    test_disconnected_and_suppressed_replacement_is_atomic(client, research, state)
                else:
                    test_attempted_delivery_cannot_be_replaced_after_timeout_disconnect_or_retry(client, research, state, patch, scenario)
        with pytest.MonkeyPatch.context() as patch:
            research, state = fake_research.__wrapped__(patch), boundaries.__wrapped__(patch)
            a, data, integration, reviewed = prepared(client, research, state)
            wid = UUID(a["X-Workspace-ID"])
            claim = client.portal.call(execution_worker.claim_next, wid)
            assert claim
            rotate(client, a, integration)
            inside, release = threading.Event(), threading.Event()
            original_compose = outreach_service.compose
            async def held_compose(*args):
                inside.set()
                assert await asyncio.to_thread(release.wait, 15)
                return await original_compose(*args)
            patch.setattr(outreach_service, "compose", held_compose)
            async def stale_worker():
                try:
                    await execution_worker.perform(wid, claim)
                except (HTTPException, ValueError):
                    return "blocked"
                raise AssertionError("Cancelled worker performed delivery")
            async def wait_for_waiters():
                async with engine.connect() as db:
                    for _ in range(100):
                        await db.execute(text("SELECT pg_stat_clear_snapshot()"))
                        count = await db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE '%workspaces%'"))
                        if count >= 2: return
                        await asyncio.sleep(.05)
                raise AssertionError("Replacement and stale worker did not wait on workspace serialization")
            with ThreadPoolExecutor(max_workers=3) as pool:
                first = pool.submit(replacement, client, a, reviewed)
                try:
                    assert inside.wait(10)
                    second = pool.submit(replacement, client, a, reviewed)
                    worker = pool.submit(client.portal.call, stale_worker)
                    client.portal.call(wait_for_waiters)
                finally:
                    release.set()
                one, two = first.result(20), second.result(20)
                assert one.status_code == two.status_code == 201
                assert one.json()["id"] == two.json()["id"]
                assert worker.result(20) == "blocked"
            client.portal.call(execution_worker.finish, wid, claim, None, "cancelled_worker")
            assert get_message(client, a, reviewed)["state"] == "cancelled"
            assert not any(call[0] == "POST" for call in state["calls"])
            async def terminal_sql_guard():
                async with AsyncSessionLocal() as db:
                    db.info.update(workspace_id=wid, workspace_role="owner")
                    connection = await db.connection()
                    try:
                        await connection.execute(text("UPDATE messages SET state='approved' WHERE id=:id"), {"id": UUID(reviewed["message"]["id"])})
                    except DBAPIError as error:
                        assert "immutable" in str(error)
                        await db.rollback()
                    else: raise AssertionError("Cancelled approval resurrected through SQL")
            client.portal.call(terminal_sql_guard)
        with pytest.MonkeyPatch.context() as patch:
            research, state = fake_research.__wrapped__(patch), boundaries.__wrapped__(patch)
            a, data, integration, reviewed = prepared(client, research, state)
            wid = UUID(a["X-Workspace-ID"])
            patch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
            sending, release = threading.Event(), threading.Event()
            original_request = providers.provider_request
            async def held_send(method, url, **kwargs):
                value = await original_request(method, url, **kwargs)
                if method == "POST":
                    sending.set()
                    assert await asyncio.to_thread(release.wait, 15)
                return value
            patch.setattr(providers, "provider_request", held_send)
            with ThreadPoolExecutor(max_workers=2) as pool:
                worker = pool.submit(client.portal.call, execution_worker.run_once, wid)
                try:
                    assert sending.wait(10)
                    cancel = pool.submit(replacement, client, a, reviewed)
                    # Wait until cancellation really blocks on the worker's lock.
                    async def waiting():
                        async with engine.connect() as db:
                            for _ in range(100):
                                await db.execute(text("SELECT pg_stat_clear_snapshot()"))
                                if await db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE '%workspaces%'")): return
                                await asyncio.sleep(.05)
                        raise AssertionError("Cancellation did not wait on dispatch")
                    client.portal.call(waiting)
                finally: release.set()
                worker.result(20)
                assert cancel.result(20).status_code == 409
            assert get_message(client, a, reviewed)["state"] == "sent"
            assert len([call for call in state["calls"] if call[0] == "POST"]) == 1
        client.portal.call(engine.dispose)


if __name__ == "__main__": run()
