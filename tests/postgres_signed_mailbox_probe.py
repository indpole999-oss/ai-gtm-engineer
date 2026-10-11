"""Actual signed HTTP callbacks racing an outreach worker on disposable PostgreSQL.

All external provider HTTP is replaced by deterministic fixtures. Run only from
test_postgres_mailbox_locks.py, which creates and migrates a unique test database.
"""
import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text
from backend.main import app
from backend.config import settings
from backend.database import AsyncSessionLocal, engine
from backend import providers, integration_service, execution_worker
from backend.inbox_models import InboundMessage, InboundReceipt
from backend.outreach_models import DeliveryEvent, Suppression
from test_live_integration_boundaries import boundaries, prepare_resend, send_event
from test_outreach import approve_draft, get_message
from test_planning_execution import approve
from test_research import fake_research
from test_workspace_security import signup


def run_signed_race():
    with pytest.MonkeyPatch.context() as patch:
        research = fake_research.__wrapped__(patch)
        state = boundaries.__wrapped__(patch)
        with TestClient(app) as client:
            headers, data, integration = prepare_resend(client, research, state)
            reviewed = approve_draft(client, headers, data)
            approve(client, headers, reviewed["plan"])
            wid = UUID(headers["X-Workspace-ID"])
            path = f"/api/v1/mailbox-webhooks/resend/{wid}/{integration['id']}/{data['sender']['id']}"
            patch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
            patch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
            sending, callback, release = threading.Event(), threading.Event(), threading.Event()
            original_request, original_connection = providers.provider_request, integration_service.connection

            async def controlled_request(method, url, **kwargs):
                result = await original_request(method, url, **kwargs)
                if method == "POST" and url.endswith("/emails"):
                    sending.set()
                    if not await asyncio.to_thread(release.wait, 15):
                        raise AssertionError("Timed out waiting to release synthetic dispatch")
                return result

            async def observed_connection(db, identity, lock=False):
                if lock and sending.is_set():
                    callback.set()
                return await original_connection(db, identity, lock=lock)

            async def wait_for_workspace():
                async with engine.connect() as db:
                    for _ in range(100):
                        await db.execute(text("SELECT pg_stat_clear_snapshot()"))
                        waiting = await db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE '%workspaces%'"))
                        if waiting:
                            return
                        await asyncio.sleep(.05)
                raise AssertionError("Signed callback did not wait on the workspace lock")

            patch.setattr(providers, "provider_request", controlled_request)
            patch.setattr(integration_service, "connection", observed_connection)
            with ThreadPoolExecutor(max_workers=2) as pool:
                worker = pool.submit(client.portal.call, execution_worker.run_once, wid)
                try:
                    assert sending.wait(10), "Worker never reached synthetic dispatch"
                    response = pool.submit(send_event, client, path, kind="email.bounced")
                    assert callback.wait(10), "Signed callback never reached locking lookup"
                    client.portal.call(wait_for_workspace)
                    assert not response.done()
                    release.set()
                    worker.result(timeout=20)
                    first = response.result(timeout=20)
                    assert first.status_code == 202, first.text
                finally:
                    release.set()
            second = send_event(client, path, kind="email.bounced")
            assert second.status_code == 202 and second.json() == first.json()
            assert get_message(client, headers, reviewed)["state"] == "sent"
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(lambda _: send_event(client, path, event_id="concurrent-inbound"), range(2)))
            assert all(reply.status_code == 202 for reply in replies)
            assert replies[0].json() == replies[1].json()

            async def persisted():
                async with AsyncSessionLocal() as db:
                    db.info.update(workspace_id=wid, workspace_role="owner")
                    assert await db.scalar(select(func.count()).select_from(DeliveryEvent)) == 3
                    assert await db.scalar(select(func.count()).select_from(Suppression)) == 1
                    assert await db.scalar(select(func.count()).select_from(InboundMessage)) == 1
                    assert await db.scalar(select(func.count()).select_from(InboundReceipt)) == 1
                await engine.dispose()
            client.portal.call(persisted)
            assert len([call for call in state["calls"] if call[0] == "POST"]) == 1
            other = signup(client, "signed-pg-other@example.com")
            assert client.get("/api/v1/inbox/messages/" + replies[0].json()["inbound_message_id"], headers=other).status_code == 404


if __name__ == "__main__":
    run_signed_race()
