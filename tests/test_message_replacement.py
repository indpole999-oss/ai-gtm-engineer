"""Offline provider responses with real HTTP and database recovery semantics."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from backend import execution_worker
from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.outreach_models import Message, MessageDraft, DeliveryEvent
from backend.planning_models import ExecutionCycle, ActionCommand, DomainEvent
from test_live_integration_boundaries import boundaries, prepare_resend, SECRET  # noqa: F401
from test_research import fake_research  # noqa: F401
from test_outreach import approve_draft, get_message, expire, post
from test_planning_execution import approve
from test_workspace_security import signup


def prepared(client, research, state):
    a, data, integration = prepare_resend(client, research, state, email=uuid4().hex + "@example.com")
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    return a, data, integration, reviewed


def rotate(client, a, integration):
    assert client.put("/api/v1/integrations/" + integration["id"], headers=a,
        json={"credentials": {"api_key": "new-synthetic-key", "webhook_secret": SECRET}}).status_code == 200
    assert client.post("/api/v1/integrations/" + integration["id"] + "/test", headers=a).status_code == 200


def replacement(client, a, reviewed, content_hash=None):
    return client.post("/api/v1/outreach/messages/" + reviewed["message"]["id"] + "/replacement", headers=a,
        json={"content_hash": content_hash or reviewed["message"]["approved_hash"]})


def test_replacement_preserves_history_requires_fresh_approval_and_deduplicates(client, fake_research, boundaries, monkeypatch):
    a, data, integration, reviewed = prepared(client, fake_research, boundaries)
    original = reviewed["message"]
    assert replacement(client, a, reviewed).status_code == 409  # No reconnect.
    rotate(client, a, integration)
    assert replacement(client, a, reviewed, "0" * 64).status_code == 409
    other = signup(client, uuid4().hex + "@example.com")
    assert replacement(client, other, reviewed).status_code == 404
    result = replacement(client, a, reviewed)
    assert result.status_code == 201, result.text
    fresh = result.json()
    assert fresh["envelope"]["replacement_for_message_id"] == original["id"]
    assert replacement(client, a, reviewed).json()["id"] == fresh["id"]
    saved = get_message(client, a, reviewed)
    assert saved["state"] == "cancelled"
    for field in ("approved_hash", "approved_by", "draft_id", "scheduled_id", "plan_id"):
        assert saved[field] == original[field]
    assert client.post("/api/v1/outreach/messages/" + original["id"] + "/retry", headers=a).status_code == 409
    assert client.post("/api/v1/outreach/drafts/" + data["draft"]["id"] + "/approve", headers=a,
        json={"reviewed": True, "content_hash": data["draft"]["content_hash"]}).status_code == 409
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    wid = UUID(a["X-Workspace-ID"])
    client.portal.call(execution_worker.run_once, wid)
    assert not any(method == "POST" for method, _, _ in boundaries["calls"])
    state = client.get("/api/v1/outreach/drafts/" + fresh["id"] + "/review", headers=a).json()
    assert state["status"] == "draft"
    data["draft"] = fresh
    new = approve_draft(client, a, data)
    client.portal.call(execution_worker.run_once, wid)
    assert not any(method == "POST" for method, _, _ in boundaries["calls"])  # Separate plan approval mandatory.
    approve(client, a, new["plan"])
    client.portal.call(execution_worker.run_once, wid)
    client.portal.call(execution_worker.run_once, wid)
    assert get_message(client, a, new)["state"] == "sent"
    assert len([c for c in boundaries["calls"] if c[0] == "POST"]) == 1
    assert replacement(client, a, reviewed).json()["id"] == fresh["id"]
    assert replacement(client, a, new).status_code == 409
    async def check():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=wid, workspace_role="owner")
            assert await db.scalar(select(func.count()).select_from(Message).where(Message.scheduled_id == UUID(original["scheduled_id"]))) == 2
            old_cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.plan_id == UUID(original["plan_id"])))
            assert old_cycle.status == "cancelled"
            old_command = await db.scalar(select(ActionCommand).where(ActionCommand.cycle_id == old_cycle.id))
            assert old_command.status == "cancelled" and old_command.lease_token is None
            assert await db.scalar(select(func.count()).select_from(DeliveryEvent).where(DeliveryEvent.message_id == UUID(original["id"]), DeliveryEvent.kind == "cancelled")) == 1
    client.portal.call(check)


@pytest.mark.parametrize("mode", ["provider_timeout", "reconnect_required", "rate_limited"])
def test_attempted_delivery_cannot_be_replaced_after_timeout_disconnect_or_retry(client, fake_research, boundaries, monkeypatch, mode):
    a, data, integration, reviewed = prepared(client, fake_research, boundaries)
    boundaries["mode"] = mode
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    wid = UUID(a["X-Workspace-ID"])
    client.portal.call(execution_worker.run_once, wid)
    assert get_message(client, a, reviewed)["attempted_at"] is not None
    boundaries["mode"] = "success"
    rotate(client, a, integration)
    assert replacement(client, a, reviewed).status_code == 409
    expire(client, a)
    client.portal.call(execution_worker.run_once, wid)
    assert len([c for c in boundaries["calls"] if c[0] == "POST"]) == 1
    assert get_message(client, a, reviewed)["state"] != "cancelled"


def test_disconnected_and_suppressed_replacement_is_atomic(client, fake_research, boundaries):
    a, data, integration, reviewed = prepared(client, fake_research, boundaries)
    assert client.put("/api/v1/integrations/" + integration["id"], headers=a,
        json={"credentials": {"api_key": "new-synthetic-key", "webhook_secret": SECRET}}).status_code == 200
    assert replacement(client, a, reviewed).status_code == 409
    assert get_message(client, a, reviewed)["state"] == "approved"
    rotate(client, a, integration)
    post(client, a, "/suppressions", {"email": "jane@example.com", "reason": "unsubscribe"})
    assert replacement(client, a, reviewed).status_code == 409
    assert get_message(client, a, reviewed)["state"] == "approved"


def test_replacement_rolls_back_when_new_draft_cannot_be_composed(client, fake_research, boundaries, monkeypatch):
    from fastapi import HTTPException
    from backend import outreach_service
    a, data, integration, reviewed = prepared(client, fake_research, boundaries)
    rotate(client, a, integration)
    async def fail(*args):
        raise HTTPException(409, "Synthetic composition failure")
    monkeypatch.setattr(outreach_service, "compose", fail)
    assert replacement(client, a, reviewed).status_code == 409
    assert get_message(client, a, reviewed)["state"] == "approved"
    cycle = client.get("/api/v1/gtm/cycles", headers=a).json()[0]
    assert cycle["status"] == "running"
    assert not any(event["kind"] == "cancelled" for event in client.get("/api/v1/outreach/delivery-events", headers=a).json())


def test_replacement_requires_owner_or_admin(client, fake_research, boundaries):
    from backend.database import WorkspaceMembership
    a, data, integration, reviewed = prepared(client, fake_research, boundaries)
    rotate(client, a, integration)
    async def downgrade_role():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="owner")
            membership = await db.scalar(select(WorkspaceMembership))
            membership.role = "member"
            await db.commit()
    client.portal.call(downgrade_role)
    assert replacement(client, a, reviewed).status_code == 403
    assert get_message(client, a, reviewed)["state"] == "approved"
