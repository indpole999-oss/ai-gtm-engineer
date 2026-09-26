"""Concurrent inbound receipts and outbox consumers on a disposable PostgreSQL DB."""
import asyncio
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError

sys.path.insert(0, str(Path.cwd() / "tests"))
from backend.main import app
from backend.database import AsyncSessionLocal, engine
from backend import execution_worker as worker, inbox_worker, inbox_service as service, outreach_service
from backend.inbox_models import MODELS, InboundMessage, InboundReceipt, InboxPause, ReplyClassification, InboxThread
from backend.outreach_models import SenderIdentity
from test_outreach import FakeProvider, setup_outreach, approve_draft, get_message
from test_planning_execution import approve
from test_research import fake_research
from test_inbox import event

role, other_workspace = sys.argv[1:3]
assert role.startswith("gaps_role_") and role.replace("_", "").isalnum()

with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as patch:
    fake = fake_research.__wrapped__(patch)
    provider = FakeProvider(str(Path(directory) / "provider.db"))
    patch.setattr(outreach_service, "delivery_provider", lambda sender: provider)
    with TestClient(app) as client:
        a, data = setup_outreach(client, fake, email="postgres-inbox@example.com")
        reviewed = approve_draft(client, a, data)
        approve(client, a, reviewed["plan"])
        wid = UUID(a["X-Workspace-ID"])
        client.portal.call(worker.run_once, wid)
        outbound = get_message(client, a, reviewed)

        async def receive():
            async with AsyncSessionLocal() as db:
                worker.bind(db, wid)
                return (await service.ingest(db, UUID(data["sender"]["id"]), service.InboundEvent(**event(outbound)))).id

        async def concurrent():
            ids = await asyncio.gather(receive(), receive())
            assert ids[0] == ids[1]
            claims = await asyncio.gather(inbox_worker.claim_next(wid), inbox_worker.claim_next(wid))
            assert sum(c is not None for c in claims) == 1
            claim = next(c for c in claims if c)
            await engine.dispose()
            assert await inbox_worker.perform(wid, claim)
            assert not await inbox_worker.perform(wid, claim)
            return ids[0]

        inbound_id = client.portal.call(concurrent)
        draft = client.post(f"/api/v1/inbox/messages/{inbound_id}/suggested-reply", headers=a)
        assert draft.status_code == 201, draft.text

        async def security():
            async with AsyncSessionLocal() as db:
                worker.bind(db, UUID(other_workspace))
                sender = SenderIdentity(email="other-inbox@example.com", provider="fake", status="connected", daily_limit=20)
                db.add(sender)
                await db.flush()
                thread = InboxThread(sender_id=sender.id, thread_key="other")
                db.add(thread)
                await db.commit()
                other_thread = thread.id
            async with AsyncSessionLocal() as db:
                worker.bind(db, wid)
                for model in (InboundMessage, InboundReceipt, InboxPause, ReplyClassification):
                    assert await db.scalar(select(func.count(model.id))) == 1
                connection = await db.connection()
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                for model in MODELS:
                    assert await connection.scalar(text(f"SELECT count(*) FROM {model.__tablename__}")) == 1
                try:
                    await connection.execute(text("UPDATE inbound_messages SET body='forged' WHERE id=:id"), {"id": inbound_id})
                except DBAPIError as error:
                    assert "immutable" in str(error)
                    await db.rollback()
                else:
                    raise AssertionError("Inbound SQL mutation was accepted")
                connection = await db.connection()
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                try:
                    await connection.execute(text("INSERT INTO inbox_thread_links(id,workspace_id,thread_id,outbound_message_id,created_at) VALUES(:id,:wid,:thread,:message,now())"),
                        {"id": uuid4(), "wid": wid, "thread": other_thread, "message": UUID(outbound["id"])})
                except DBAPIError as error:
                    assert "foreign key" in str(error).lower()
                    await db.rollback()
                else:
                    raise AssertionError("Cross-workspace thread reference accepted")
                connection = await db.connection()
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                await connection.execute(text("SELECT set_config('app.workspace_id', :wid, true)"), {"wid": str(uuid4())})
                for model in MODELS:
                    assert await connection.scalar(text(f"SELECT count(*) FROM {model.__tablename__}")) == 0
            await engine.dispose()

        client.portal.call(security)
        assert provider.calls == 1
