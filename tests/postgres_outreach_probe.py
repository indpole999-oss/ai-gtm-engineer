"""Exercise the outreach HTTP/worker path against an Alembic-migrated PostgreSQL DB."""
import asyncio
import sys
import tempfile
from pathlib import Path
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, select, func
from sqlalchemy.exc import DBAPIError

sys.path.insert(0, str(Path.cwd() / "tests"))
from backend.main import app
from backend.database import AsyncSessionLocal, engine
from backend.outreach_models import ScheduledMessage, MessageDraft, DraftReviewEvent
from backend.research_service import scoped_record
from backend.tenancy import WorkspaceContext
from backend import execution_worker as worker, outreach_service as service
from test_outreach import FakeProvider, ready, get_message, post, BASE
from test_research import fake_research


with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as patch:
    fake = fake_research.__wrapped__(patch)
    provider = FakeProvider(str(Path(directory) / "provider.db"), "lost_ack")
    patch.setattr(service, "delivery_provider", lambda sender: provider)
    with TestClient(app) as client:
        a, data, reviewed, cycle = ready(client, fake)
        wid = UUID(a["X-Workspace-ID"])

        async def concurrent_claims():
            claims = await asyncio.gather(worker.claim_next(wid), worker.claim_next(wid))
            assert sum(c is not None for c in claims) == 1
            return next(c for c in claims if c)

        claim = client.portal.call(concurrent_claims)
        try:
            client.portal.call(worker.perform, wid, claim)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected lost provider acknowledgement")
        assert get_message(client, a, reviewed)["state"] == "reconciling"
        # New provider object and DB pool simulate independent worker restart.
        client.portal.call(engine.dispose)
        replacement = FakeProvider(provider.path)
        patch.setattr(service, "delivery_provider", lambda sender: replacement)
        output = client.portal.call(worker.perform, wid, claim)
        client.portal.call(worker.finish, wid, claim, output)
        assert provider.calls == 1 and replacement.calls == 0
        message = get_message(client, a, reviewed)
        assert message["state"] == "sent"

        async def immutable_approval():
            async with AsyncSessionLocal() as db:
                worker.bind(db, wid)
                connection = await db.connection()
                try:
                    await connection.execute(text("UPDATE messages SET approved_hash='forged' WHERE id=:id"), {"id": UUID(message["id"])})
                except DBAPIError as error:
                    assert "immutable" in str(error)
                    await db.rollback()
                else:
                    raise AssertionError("Message approval SQL mutation accepted")
            await engine.dispose()

        client.portal.call(immutable_approval)

        # Concurrent independent sessions exercise the real PostgreSQL workspace lock.
        version = post(client, a, f"/sequences/{data['sequence']['id']}/versions",
            {"steps": [{"delay_seconds": 0, "purpose": "Concurrent synthetic review"}]})
        enrollment = post(client, a, "/enrollments", {
            **{key: data["enrollment"][key] for key in ("contact_id", "sender_id", "research_job_id")},
            "version_id": version["id"]})
        scheduled = next(row for row in client.get(BASE + "/scheduled", headers=a).json() if row["enrollment_id"] == enrollment["id"])
        actor = UUID(data["draft"]["created_by"])
        async def compose_concurrently():
            async def compose():
                async with AsyncSessionLocal() as db:
                    worker.bind(db, wid)
                    row = await service.compose(db, await scoped_record(db, ScheduledMessage, UUID(scheduled["id"])), actor)
                    return row.id
            ids = await asyncio.gather(compose(), compose())
            assert ids[0] == ids[1]
            return ids[0]
        draft_id = client.portal.call(compose_concurrently)
        draft = client.get(BASE + "/drafts/" + str(draft_id), headers=a).json()
        state = client.get(BASE + "/drafts/" + str(draft_id) + "/review", headers=a).json()
        state = post(client, a, "/drafts/" + str(draft_id) + "/submit",
            {"content_hash": draft["content_hash"], "expected_revision": state["revision"]})
        async def approve_concurrently():
            async def approve():
                async with AsyncSessionLocal() as db:
                    worker.bind(db, wid)
                    row = await service.approve_message(db, await scoped_record(db, MessageDraft, draft_id),
                        WorkspaceContext(wid, actor, "owner"), draft["content_hash"], state["revision"])
                    return row.id
            ids = await asyncio.gather(approve(), approve())
            assert ids[0] == ids[1]
            async with AsyncSessionLocal() as db:
                worker.bind(db, wid)
                assert await db.scalar(select(func.count()).select_from(DraftReviewEvent).where(
                    DraftReviewEvent.draft_id == draft_id, DraftReviewEvent.action == "approved")) == 1
                connection = await db.connection()
                try:
                    await connection.execute(text("UPDATE draft_review_events SET reason='tampered' WHERE draft_id=:id"), {"id": draft_id})
                except DBAPIError as error:
                    assert "immutable" in str(error)
                    await db.rollback()
                else:
                    raise AssertionError("Review history SQL mutation accepted")
            await engine.dispose()
        client.portal.call(approve_concurrently)
