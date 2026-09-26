"""No network provider calls: a durable, deterministic external-provider ledger."""
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from uuid import UUID
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from backend import outreach_service as service, execution_worker as worker
from backend.database import AsyncSessionLocal, engine, WorkspaceMembership, Contact
from backend.outreach_models import Message, MessageDraft, SequenceVersion, ScheduledMessage, SenderIdentity, Enrollment
from backend.planning_models import ActionCommand
from test_workspace_security import signup, company
from test_research import published, create_job, execute_job, fake_research  # noqa: F401
from test_planning_execution import approve

BASE = "/api/v1/outreach"


class FakeProvider:
    durable_idempotency = True
    def __init__(self, path, mode="accepted"):
        self.path, self.mode, self.calls = path, mode, 0
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS accepted (key TEXT PRIMARY KEY, id TEXT NOT NULL)")

    async def lookup(self, key):
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT id FROM accepted WHERE key=?", (key,)).fetchone()
        return {"status": "accepted", "id": row[0]} if row else None

    async def send(self, key, envelope):
        self.calls += 1
        if self.mode == "failure":
            return {"status": "rejected"}
        if self.mode == "unavailable":
            raise RuntimeError("fake provider unavailable")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR IGNORE INTO accepted VALUES (?,?)", (key, "fake-" + key))
        if self.mode == "lost_ack":
            raise RuntimeError("fake response lost after provider accepted")
        return await self.lookup(key)


@pytest.fixture
def provider(tmp_path, monkeypatch):
    adapter = FakeProvider(str(tmp_path / "provider.db"))
    monkeypatch.setattr(service, "delivery_provider", lambda sender: adapter)
    return adapter


def post(client, headers, path, body=None):
    r = client.post(BASE + path, headers=headers, json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def setup_outreach(client, fake_research, email="outreach@example.com", steps=None):
    a = signup(client, email)
    brain, account = published(client, a), company(client, a)
    job = create_job(client, a, brain, account)
    assert execute_job(client, a, job["id"]).status_code == 200
    contact = client.post("/api/v1/contacts/", headers=a, json={"company_id": account["id"], "first_name": "Jane", "last_name": "Buyer", "email": "jane@example.com"}).json()
    campaign = post(client, a, "/campaigns", {"name": "Evidence-led outreach"})
    sequence = post(client, a, "/sequences", {"name": "Initial sequence", "campaign_id": campaign["id"]})
    version = post(client, a, f"/sequences/{sequence['id']}/versions", {"steps": steps or [{"delay_seconds": 0, "purpose": "Introduction"}]})
    sender = post(client, a, "/senders", {"email": "sender@example.com", "provider": "fake"})
    enrollment = post(client, a, "/enrollments", {"version_id": version["id"], "contact_id": contact["id"], "sender_id": sender["id"], "research_job_id": job["id"]})
    scheduled = client.get(BASE + "/scheduled", headers=a).json()[-1]
    draft = post(client, a, f"/scheduled/{scheduled['id']}/drafts")
    return a, {"campaign": campaign, "sequence": sequence, "version": version, "sender": sender, "enrollment": enrollment, "scheduled": scheduled, "draft": draft}


def approve_draft(client, a, data):
    d = data["draft"]
    return post(client, a, f"/drafts/{d['id']}/approve", {"content_hash": d["content_hash"], "reviewed": True})


def get_message(client, a, reviewed):
    return client.get(BASE + "/messages/" + reviewed["message"]["id"], headers=a).json()


def ready(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    reviewed = approve_draft(client, a, data)
    cycle = approve(client, a, reviewed["plan"])
    return a, data, reviewed, cycle


def expire(client, a, claim=None):
    async def run():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            command = await db.scalar(select(ActionCommand))
            command.due_at = datetime.utcnow() - timedelta(seconds=1)
            if claim:
                command.lease_until = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    client.portal.call(run)


def test_drafting_and_message_approval_do_not_send_plan_approval_required(client, fake_research, provider):
    a, data = setup_outreach(client, fake_research)
    wid = UUID(a["X-Workspace-ID"])
    assert not client.portal.call(worker.run_once, wid)
    assert client.get(BASE + "/messages", headers=a).json() == []
    d = data["draft"]
    assert client.post(BASE + f"/drafts/{d['id']}/approve", headers=a, json={"content_hash": "0" * 64, "reviewed": True}).status_code == 409
    reviewed = approve_draft(client, a, data)
    assert not client.portal.call(worker.run_once, wid)
    assert provider.calls == 0
    assert approve_draft(client, a, data)["message"]["id"] == reviewed["message"]["id"]
    approve(client, a, reviewed["plan"])
    client.portal.call(worker.run_once, wid)
    message = get_message(client, a, reviewed)
    assert message["state"] == "sent", message
    assert message["provider_message_id"] and message["accepted_at"]
    assert provider.calls == 1
    assert not client.portal.call(worker.run_once, wid)
    assert len(client.get(BASE + "/delivery-events", headers=a).json()) == 1
    assert data["draft"]["envelope"]["evidence_id"]
    assert data["draft"]["envelope"]["brain_hash"]


@pytest.mark.parametrize("mode", ["failure", "unavailable"])
def test_provider_failure_never_sent_and_bounded_retry(client, fake_research, provider, mode):
    a, data, reviewed, cycle = ready(client, fake_research)
    provider.mode = mode
    for _ in range(3):
        expire(client, a)
        client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
        m = get_message(client, a, reviewed)
        assert m["state"] != "sent" and m["accepted_at"] is None and m["provider_message_id"] is None
    state = client.get("/api/v1/gtm/cycles/" + cycle["id"], headers=a).json()
    assert state["status"] == "failed"
    provider.mode = "accepted"
    post(client, a, "/messages/" + reviewed["message"]["id"] + "/retry")
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert get_message(client, a, reviewed)["state"] == "sent"


def test_lost_ack_restart_reconciles_without_duplicate_send(client, fake_research, provider, monkeypatch):
    a, data, reviewed, cycle = ready(client, fake_research)
    wid = UUID(a["X-Workspace-ID"])
    provider.mode = "lost_ack"
    client.portal.call(worker.run_once, wid)
    assert get_message(client, a, reviewed)["state"] == "reconciling"
    client.portal.call(engine.dispose)
    replacement = FakeProvider(provider.path)
    monkeypatch.setattr(service, "delivery_provider", lambda sender: replacement)
    expire(client, a)
    client.portal.call(worker.run_once, wid)
    assert get_message(client, a, reviewed)["state"] == "sent"
    assert provider.calls == 1 and replacement.calls == 0


def test_crash_after_send_before_ack_and_stale_lease(client, fake_research, provider):
    a, data, reviewed, cycle = ready(client, fake_research)
    wid = UUID(a["X-Workspace-ID"])
    first = client.portal.call(worker.claim_next, wid)
    output = client.portal.call(worker.perform, wid, first)
    expire(client, a, first)
    second = client.portal.call(worker.claim_next, wid)
    client.portal.call(worker.finish, wid, first, output)
    result = client.portal.call(worker.perform, wid, second)
    client.portal.call(worker.finish, wid, second, result)
    assert provider.calls == 1
    assert client.get("/api/v1/gtm/cycles/" + cycle["id"], headers=a).json()["status"] == "completed"


@pytest.mark.parametrize("reason", ["suppressed", "unsubscribe"])
def test_suppression_after_approval_blocks_worker(client, fake_research, provider, reason):
    a, data, reviewed, cycle = ready(client, fake_research)
    post(client, a, "/suppressions", {"email": "JANE@example.com", "reason": reason})
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 0
    assert get_message(client, a, reviewed)["state"] == "blocked"
    assert client.post(BASE + f"/scheduled/{data['scheduled']['id']}/drafts", headers=a).status_code == 409


def test_cross_workspace_reads_and_relationships(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    b = signup(client, "other@example.com")
    for resource, key in [("campaigns", "campaign"), ("sequences", "sequence"), ("versions", "version"), ("senders", "sender"), ("enrollments", "enrollment"), ("scheduled", "scheduled"), ("drafts", "draft")]:
        assert client.get(BASE + "/" + resource, headers=b).json() == []
        assert client.get(BASE + "/" + resource + "/" + data[key]["id"], headers=b).status_code == 404
    assert client.post(BASE + "/sequences", headers=b, json={"name": "forged", "campaign_id": data["campaign"]["id"]}).status_code == 404
    d = data["draft"]
    assert client.post(BASE + f"/drafts/{d['id']}/approve", headers=b, json={"content_hash": d["content_hash"], "reviewed": True}).status_code == 404


def test_versions_pinned_and_snapshots_immutable(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    v2 = post(client, a, f"/sequences/{data['sequence']['id']}/versions", {"steps": [{"delay_seconds": 100, "purpose": "New definition"}]})
    assert v2["number"] == 2
    assert client.get(BASE + "/enrollments/" + data["enrollment"]["id"], headers=a).json()["version_id"] == data["version"]["id"]
    async def tamper(model, key, field, value):
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            row = await db.scalar(select(model).where(model.id == UUID(key)))
            setattr(row, field, value)
            with pytest.raises(HTTPException, match="immutable"):
                await db.commit()
    client.portal.call(tamper, SequenceVersion, data["version"]["id"], "content_hash", "x")
    client.portal.call(tamper, MessageDraft, data["draft"]["id"], "envelope", {})


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_non_admin_cannot_approve(client, fake_research, role):
    a, data = setup_outreach(client, fake_research)
    async def change():
        async with AsyncSessionLocal() as db:
            m = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            m.role = role
            await db.commit()
    client.portal.call(change)
    d = data["draft"]
    assert client.post(BASE + f"/drafts/{d['id']}/approve", headers=a, json={"content_hash": d["content_hash"], "reviewed": True}).status_code == 403


def test_default_provider_is_disabled(client, fake_research):
    a, data, reviewed, cycle = ready(client, fake_research)
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert get_message(client, a, reviewed)["state"] != "sent"


def test_sequence_waits_without_consuming_attempts(client, fake_research, provider):
    a, data = setup_outreach(client, fake_research, steps=[{"delay_seconds": 0, "purpose": "First"}, {"delay_seconds": 0, "purpose": "Follow up"}])
    schedules = client.get(BASE + "/scheduled", headers=a).json()
    steps = {s["id"]: s["position"] for s in client.get(BASE + "/steps", headers=a).json()}
    later = next(s for s in schedules if steps[s["sequence_step_id"]] == 1)
    data["draft"] = post(client, a, f"/scheduled/{later['id']}/drafts")
    reviewed = approve_draft(client, a, data)
    cycle = approve(client, a, reviewed["plan"])
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 0
    assert client.get("/api/v1/gtm/cycles/" + cycle["id"], headers=a).json()["commands"][0]["attempts"] == 0


def test_future_schedule_is_not_claimed(client, fake_research, provider):
    a, data = setup_outreach(client, fake_research, steps=[{"delay_seconds": 3600, "purpose": "Tomorrow"}])
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 0


def test_delivery_event_is_separate_idempotent_and_suppresses(client, fake_research, provider):
    a, data, reviewed, cycle = ready(client, fake_research)
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    m = get_message(client, a, reviewed)
    async def record():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            await service.record_delivery_event(db, UUID(m["id"]), m["provider_message_id"], "bounce-1", "bounce")
            await service.record_delivery_event(db, UUID(m["id"]), m["provider_message_id"], "bounce-1", "bounce")
    client.portal.call(record)
    assert get_message(client, a, reviewed)["state"] == "sent"
    assert len(client.get(BASE + "/delivery-events", headers=a).json()) == 2
    assert client.get(BASE + "/suppressions", headers=a).json()[0]["reason"] == "bounce"


@pytest.mark.parametrize("limit", [1, 20])
def test_recipient_and_sender_daily_limits(client, fake_research, provider, limit):
    a, data, reviewed, cycle = ready(client, fake_research)
    wid = UUID(a["X-Workspace-ID"])
    async def set_limit():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            sender = await db.scalar(select(SenderIdentity).where(SenderIdentity.id == UUID(data["sender"]["id"])))
            sender.daily_limit = limit
            await db.commit()
    client.portal.call(set_limit)
    client.portal.call(worker.run_once, wid)
    v2 = post(client, a, f"/sequences/{data['sequence']['id']}/versions", {"steps": [{"delay_seconds": 0, "purpose": "Another"}]})
    inputs = {k: data["enrollment"][k] for k in ("contact_id", "sender_id", "research_job_id")}
    new = post(client, a, "/enrollments", {**inputs, "version_id": v2["id"]})
    scheduled = next(s for s in client.get(BASE + "/scheduled", headers=a).json() if s["enrollment_id"] == new["id"])
    data["draft"] = post(client, a, f"/scheduled/{scheduled['id']}/drafts")
    second = approve_draft(client, a, data)
    approve(client, a, second["plan"])
    client.portal.call(worker.run_once, wid)
    assert get_message(client, a, second)["state"] == "blocked"
    assert provider.calls == 1


def test_revoked_message_approver_and_paused_enrollment_block(client, fake_research, provider):
    a, data, reviewed, cycle = ready(client, fake_research)
    post(client, a, f"/enrollments/{data['enrollment']['id']}/control", {"status": "paused"})
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 0

    post(client, a, f"/enrollments/{data['enrollment']['id']}/control", {"status": "active"})
    async def revoke():
        async with AsyncSessionLocal() as db:
            m = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            m.role = "member"
            await db.commit()
    client.portal.call(revoke)
    expire(client, a)
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 0


def test_unknown_lookup_never_blindly_resends(client, fake_research, provider, monkeypatch):
    a, data, reviewed, cycle = ready(client, fake_research)
    provider.mode = "lost_ack"
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    async def unavailable(key):
        raise RuntimeError("Lookup cannot determine outcome")
    monkeypatch.setattr(provider, "lookup", unavailable)
    expire(client, a)
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 1
    assert get_message(client, a, reviewed)["state"] == "reconciling"


@pytest.mark.parametrize("change", ["recipient", "sender"])
def test_recipient_or_sender_change_after_approval_blocks(client, fake_research, provider, change):
    a, data, reviewed, cycle = ready(client, fake_research)
    async def mutate():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            if change == "recipient":
                row = await db.scalar(select(Contact).where(Contact.id == UUID(data["enrollment"]["contact_id"])))
                row.email = "changed@example.com"
            else:
                row = await db.scalar(select(SenderIdentity).where(SenderIdentity.id == UUID(data["sender"]["id"])))
                row.status = "disconnected"
            await db.commit()
    client.portal.call(mutate)
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert provider.calls == 0
    assert get_message(client, a, reviewed)["state"] == "blocked"


def test_pause_between_intent_commit_and_dispatch_is_rechecked(client, fake_research, provider, monkeypatch):
    a, data, reviewed, cycle = ready(client, fake_research)
    real_lock = service.lock_workspace
    calls = 0
    async def interleaved_lock(db):
        nonlocal calls
        calls += 1
        if calls == 2:
            async with AsyncSessionLocal() as other:
                worker.bind(other, UUID(a["X-Workspace-ID"]))
                enrollment = await other.scalar(select(Enrollment).where(Enrollment.id == UUID(data["enrollment"]["id"])))
                enrollment.status = "paused"
                await other.commit()
        await real_lock(db)
    monkeypatch.setattr(service, "lock_workspace", interleaved_lock)
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert calls == 2 and provider.calls == 0
    assert get_message(client, a, reviewed)["state"] != "sent"
