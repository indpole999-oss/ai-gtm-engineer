"""Exercise the outreach HTTP/worker path against an Alembic-migrated PostgreSQL DB."""
import asyncio
import sys
import tempfile
from pathlib import Path
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

sys.path.insert(0, str(Path.cwd() / "tests"))
from backend.main import app
from backend.database import AsyncSessionLocal, engine
from backend import execution_worker as worker, outreach_service as service
from test_outreach import FakeProvider, ready, get_message
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
