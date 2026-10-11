"""Actual HTTP/API/SQLite boundaries, deterministic provider HTTP only. No live calls."""
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import pytest
import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select, func
from backend.config import settings
from backend import providers, execution_worker
from backend.database import AsyncSessionLocal, Integration
from backend.outreach_models import SenderIdentity, Message, DeliveryEvent
from backend.inbox_models import InboundMessage, InboundReceipt
from backend.security import decrypt_credentials
from test_workspace_security import signup
from test_research import fake_research  # noqa: F401
from test_outreach import setup_outreach, post, approve_draft, get_message, expire
from test_planning_execution import approve

SECRET = "whsec_" + base64.b64encode(b"deterministic-webhook-secret-32b!!").decode()
EMAIL_ID = "72e3606f-64ef-4410-b2a1-1db75b051ca8"


@pytest.fixture
def boundaries(monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for name in ["OUTBOUND_EMAIL_ENABLED", "MAILBOX_INGESTION_ENABLED", "CRM_READS_ENABLED"]:
        monkeypatch.setattr(settings, name, False)
    state = {"calls": [], "mode": "success", "recipient": "sender@example.com", "body": "Please unsubscribe me.", "sent": None, "reply_to": None}
    async def request(method, url, **kwargs):
        state["calls"].append((method, url, kwargs))
        if state["mode"] in {"rate_limited", "reconnect_required", "provider_unavailable", "provider_timeout"}:
            raise providers.ProviderError(state["mode"])
        if url.endswith("/domains"):
            return {"data": [{"name": "example.com", "status": "verified"}]}
        if "/receiving/" in url:
            return {"id": EMAIL_ID, "from": "Jane Buyer <jane@example.com>", "to": [state["recipient"]],
                    "subject": "Re: question", "text": state["body"], "headers": {"in-reply-to": state["reply_to"]} if state["reply_to"] else {},
                    "created_at": "2026-10-10T00:00:00Z", "authentication": {"dmarc": "pass"}}
        if method == "POST" and url.endswith("/emails"):
            state["sent"] = {"id": EMAIL_ID, "from": kwargs["json"]["from"], "to": kwargs["json"]["to"],
                "subject": kwargs["json"]["subject"], "text": kwargs["json"]["text"], "tags": kwargs["json"]["tags"],
                "created_at": datetime.utcnow().isoformat() + "Z", "message_id": "<synthetic-rfc-id@example.com>"}
            if state["mode"] == "lost_ack": raise providers.ProviderError("provider_unavailable")
            if state["mode"] == "malformed": return {}
            return {"id": EMAIL_ID}
        if url.endswith("/emails/" + EMAIL_ID): return state["sent"] or {}
        if "/crm/v3/objects/" in url:
            return {"id": url.rsplit("/", 1)[1], "properties": {"email": "jane@example.com"}}
        if "/sobjects/" in url:
            return {"Id": url.rsplit("/", 1)[1], "Name": "Synthetic account"}
        return {}
    monkeypatch.setattr(providers, "provider_request", request)
    return state


def connection(client, headers, provider="resend"):
    category = "email" if provider == "resend" else "crm"
    config = {"from_email": "sender@example.com"} if provider == "resend" else {"instance_url": "https://synthetic.my.salesforce.com"} if provider == "salesforce" else {}
    result = client.post("/api/v1/integrations", headers=headers, json={"category": category,
        "provider": provider, "auth_type": "bearer" if provider == "salesforce" else "api_key",
        "credentials": {"api_key": "synthetic-token-only", "webhook_secret": SECRET}, "config": config})
    assert result.status_code == 200, result.text
    row = result.json()
    assert row["status"] == "disconnected" and "synthetic-token-only" not in result.text and SECRET not in result.text
    checked = client.post("/api/v1/integrations/" + row["id"] + "/test", headers=headers)
    assert checked.json()["integration"]["health"] == "healthy", checked.text
    return row


def mailbox(client, boundaries):
    headers = signup(client, "signed-inbound@example.com")
    integration = connection(client, headers)
    sender = post(client, headers, "/senders", {"email": "sender@example.com", "provider": "resend", "integration_id": integration["id"]})
    path = "/api/v1/mailbox-webhooks/resend/" + headers["X-Workspace-ID"] + "/" + integration["id"] + "/" + sender["id"]
    return headers, integration, sender, path


def signed(kind="email.received", event_id="event-1", timestamp=None):
    raw = json.dumps({"type": kind, "data": {"email_id": EMAIL_ID}}, separators=(",", ":")).encode()
    timestamp = str(timestamp or int(time.time()))
    signature = base64.b64encode(hmac.new(base64.b64decode(SECRET[6:]), event_id.encode() + b"." + timestamp.encode() + b"." + raw, hashlib.sha256).digest()).decode()
    return raw, {"svix-id": event_id, "svix-timestamp": timestamp, "svix-signature": "v1," + signature}


def send_event(client, path, **kwargs):
    raw, headers = signed(**kwargs)
    return client.post(path, content=raw, headers=headers)


def test_signed_inbound_persistence_dedup_suppression_and_isolation(client, boundaries, monkeypatch):
    a, integration, sender, path = mailbox(client, boundaries)
    assert send_event(client, path).status_code == 503
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    first, second = send_event(client, path), send_event(client, path)
    assert first.status_code == second.status_code == 202, first.text
    assert first.json() == second.json()
    assert len(client.get("/api/v1/inbox/threads", headers=a).json()) == 1
    async def persisted():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="owner")
            saved = await db.get(Integration, UUID(integration["id"]))
            assert isinstance(saved.credentials, str) and "synthetic-token-only" not in saved.credentials
            assert decrypt_credentials(saved.credentials)["webhook_secret"] == SECRET
            return await db.scalar(select(func.count()).select_from(InboundMessage)), await db.scalar(select(func.count()).select_from(InboundReceipt))
    assert client.portal.call(persisted) == (1, 1)
    assert client.get("/api/v1/outreach/suppressions", headers=a).json()[0]["email"] == "jane@example.com"
    b = signup(client, "signed-inbound-other@example.com")
    assert client.get("/api/v1/inbox/messages/" + first.json()["inbound_message_id"], headers=b).status_code == 404
    assert client.get("/api/v1/integrations/" + integration["id"], headers=b).status_code == 404
    assert send_event(client, path.replace(a["X-Workspace-ID"], b["X-Workspace-ID"])).status_code == 404


def test_invalid_webhook_never_acquires_mutation_locks(client, boundaries, monkeypatch):
    _, _, _, path = mailbox(client, boundaries)
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    from backend import integration_service
    original = integration_service.connection
    locks = []
    async def tracked(db, integration_id, lock=False):
        if lock:
            locks.append(integration_id)
        return await original(db, integration_id, lock=lock)
    monkeypatch.setattr(integration_service, "connection", tracked)
    raw, headers = signed()
    headers["svix-signature"] = "v1,invalid"
    assert client.post(path, content=raw, headers=headers).status_code == 401
    assert locks == []


def test_receipt_failure_rolls_back_acceptance_audit_and_suppression(client, fake_research, boundaries, monkeypatch):
    from fastapi import HTTPException
    from backend import outreach_service
    a, data, integration = prepare_resend(client, fake_research, boundaries)
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    boundaries["mode"] = "lost_ack"
    wid = UUID(a["X-Workspace-ID"])
    client.portal.call(execution_worker.run_once, wid)
    boundaries["mode"] = "success"
    path = f"/api/v1/mailbox-webhooks/resend/{wid}/{integration['id']}/{data['sender']['id']}"
    original = outreach_service.record_delivery_event
    async def fail_after_safety_writes(*args, **kwargs):
        await original(*args, **kwargs)
        raise HTTPException(503, "Synthetic transaction failure")
    monkeypatch.setattr(outreach_service, "record_delivery_event", fail_after_safety_writes)
    assert send_event(client, path, kind="email.bounced").status_code == 503
    assert get_message(client, a, reviewed)["state"] == "reconciling"
    assert client.get("/api/v1/outreach/suppressions", headers=a).json() == []
    async def receipts():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=wid, workspace_role="owner")
            return await db.scalar(select(func.count()).select_from(DeliveryEvent))
    assert client.portal.call(receipts) == 0
    audits = client.get(f"/api/v1/integrations/{integration['id']}/audit", headers=a).json()
    assert "mail_receipt_verified" not in str(audits)
    monkeypatch.setattr(outreach_service, "record_delivery_event", original)
    first = send_event(client, path, kind="email.bounced")
    second = send_event(client, path, kind="email.bounced")
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert get_message(client, a, reviewed)["state"] == "sent"
    assert len(client.get("/api/v1/outreach/suppressions", headers=a).json()) == 1
    assert client.portal.call(receipts) == 3  # acceptance, RFC alias, bounce
    assert len([call for call in boundaries["calls"] if call[0] == "POST"]) == 1


@pytest.mark.parametrize("case", ["tampered", "stale", "signature", "missing", "oversize"])
def test_webhook_rejects_before_provider_fetch(client, boundaries, monkeypatch, case):
    _, _, _, path = mailbox(client, boundaries)
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    raw, headers = signed(timestamp=int(time.time()) - 1000 if case == "stale" else None)
    if case == "tampered": raw += b" "
    if case == "signature": headers["svix-signature"] = "v1,bad"
    if case == "missing": headers = {}
    if case == "oversize": raw = b"x" * 1048577
    before = len(boundaries["calls"])
    result = client.post(path, content=raw, headers=headers)
    assert result.status_code == (413 if case == "oversize" else 401)
    assert len(boundaries["calls"]) == before


def test_webhook_retry_errors_conflicts_and_mailbox_binding(client, boundaries, monkeypatch):
    a, integration, _, path = mailbox(client, boundaries)
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    boundaries["mode"] = "rate_limited"
    failure = send_event(client, path)
    assert failure.status_code == 503 and failure.headers["Retry-After"] == "60"
    assert client.get("/api/v1/inbox/threads", headers=a).json() == []
    assert client.get("/api/v1/integrations/" + integration["id"] + "/audit", headers=a).json()[0]["action"] == "mailbox_fetch_failed"
    boundaries["mode"] = "success"
    boundaries["recipient"] = "other@example.com"
    assert send_event(client, path).status_code == 409
    boundaries["recipient"] = "sender@example.com"
    assert send_event(client, path).status_code == 202
    boundaries["body"] = "Conflicting content"
    assert send_event(client, path).status_code == 409


@pytest.mark.parametrize("provider", ["hubspot", "salesforce"])
def test_crm_reads_permissions_audit_and_write_denial(client, boundaries, monkeypatch, provider):
    a = signup(client, "crm-read@example.com")
    row = connection(client, a, provider)
    path = "/api/v1/integrations/" + row["id"] + "/crm/contact/123"
    before = len(boundaries["calls"])
    assert client.get(path, headers=a).status_code == 409
    assert len(boundaries["calls"]) == before
    monkeypatch.setattr(settings, "CRM_READS_ENABLED", True)
    result = client.get(path, headers=a)
    assert result.status_code == 200 and result.json()["write_available"] is False
    assert client.get(path.replace("contact/123", "arbitrary/123"), headers=a).status_code == 409
    b = signup(client, "crm-read-other@example.com")
    assert client.get(path, headers=b).status_code == 404
    boundaries["mode"] = "reconnect_required"
    assert client.get(path, headers=a).status_code == 409
    saved = client.get("/api/v1/integrations/" + row["id"], headers=a).json()
    assert saved["reconnect_required"] and saved["status"] == "error"
    assert {x["action"] for x in client.get("/api/v1/integrations/" + row["id"] + "/audit", headers=a).json()} >= {"crm_read_verified", "crm_read_failed"}
    assert all(method == "GET" for method, _, _ in boundaries["calls"])
    from backend.crm_transport import CRMReadTransport
    from types import SimpleNamespace
    adapter = CRMReadTransport(SimpleNamespace(id=uuid4()), {})
    with pytest.raises(providers.ProviderError, match="crm_atomic_writes_not_supported"):
        client.portal.call(adapter.apply, "namespace", "key", {})


def prepare_resend(client, fake_research, boundaries):
    a, data = setup_outreach(client, fake_research, compose_draft=False)
    integration = connection(client, a)
    async def bind_sender():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="owner")
            sender = await db.get(SenderIdentity, UUID(data["sender"]["id"]))
            sender.provider, sender.integration_id = "resend", UUID(integration["id"])
            await db.commit()
    client.portal.call(bind_sender)
    data["draft"] = post(client, a, "/scheduled/" + data["scheduled"]["id"] + "/drafts")
    return a, data, integration


def test_resend_approval_receipts_pause_and_no_duplicate_dispatch(client, fake_research, boundaries, monkeypatch):
    a, data, integration = prepare_resend(client, fake_research, boundaries)
    wid = UUID(a["X-Workspace-ID"])
    assert not client.portal.call(execution_worker.run_once, wid)
    reviewed = approve_draft(client, a, data)
    assert not client.portal.call(execution_worker.run_once, wid)
    approve(client, a, reviewed["plan"])
    client.portal.call(execution_worker.run_once, wid)
    assert get_message(client, a, reviewed)["error_code"] == "outbound_email_paused"
    assert not any(method == "POST" for method, _, _ in boundaries["calls"])
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    expire(client, a)
    client.portal.call(execution_worker.run_once, wid)
    sent = get_message(client, a, reviewed)
    assert sent["state"] == "sent" and sent["provider_message_id"] == EMAIL_ID
    assert not client.portal.call(execution_worker.run_once, wid)
    calls = [c for c in boundaries["calls"] if c[0] == "POST"]
    assert len(calls) == 1 and calls[0][2]["headers"]["Idempotency-Key"] == f"{wid}:{sent['id']}"
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    path = f"/api/v1/mailbox-webhooks/resend/{wid}/{integration['id']}/{data['sender']['id']}"
    first = send_event(client, path, kind="email.bounced")
    assert first.status_code == 202, first.text
    assert send_event(client, path, kind="email.bounced").json() == first.json()
    events = client.get("/api/v1/outreach/delivery-events", headers=a).json()
    assert [e["kind"] for e in events].count("accepted") == 1
    assert [e["kind"] for e in events].count("bounce") == 1
    assert any(r["email"] == "jane@example.com" for r in client.get("/api/v1/outreach/suppressions", headers=a).json())


@pytest.mark.parametrize("mode", ["provider_unavailable", "provider_timeout", "malformed", "rate_limited"])
def test_resend_uncertainty_and_bounded_retry(client, fake_research, boundaries, monkeypatch, mode):
    a, data, _ = prepare_resend(client, fake_research, boundaries)
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    boundaries["mode"] = mode
    wid = UUID(a["X-Workspace-ID"])
    client.portal.call(execution_worker.run_once, wid)
    assert get_message(client, a, reviewed)["state"] == "reconciling"
    boundaries["mode"] = "success"
    expire(client, a)
    client.portal.call(execution_worker.run_once, wid)
    message = get_message(client, a, reviewed)
    assert message["state"] == ("sent" if mode == "rate_limited" else "reconciling")
    assert len([c for c in boundaries["calls"] if c[0] == "POST"]) == (2 if mode == "rate_limited" else 1)


def test_provider_http_errors_are_safe_and_bounded(monkeypatch):
    real_client = httpx.AsyncClient
    def factory(**kwargs):
        return real_client(**kwargs, transport=httpx.MockTransport(lambda req: httpx.Response(429, json={"secret": "must-not-escape"})))
    monkeypatch.setattr(providers.httpx, "AsyncClient", factory)
    import asyncio
    with pytest.raises(providers.ProviderError, match="^rate_limited$"):
        asyncio.run(providers.provider_request("GET", "https://api.resend.com/domains"))


def test_provider_response_size_limit(monkeypatch):
    real_client = httpx.AsyncClient
    def factory(**kwargs):
        return real_client(**kwargs, transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 2097153)))
    monkeypatch.setattr(providers.httpx, "AsyncClient", factory)
    import asyncio
    with pytest.raises(providers.ProviderError, match="^provider_response_too_large$"):
        asyncio.run(providers.provider_request("GET", "https://api.resend.com/domains"))


def test_lost_ack_recovers_only_from_authenticated_matching_receipt_and_links_rfc_reply(client, fake_research, boundaries, monkeypatch):
    a, data, integration = prepare_resend(client, fake_research, boundaries)
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "MAILBOX_INGESTION_ENABLED", True)
    boundaries["mode"] = "lost_ack"
    wid = UUID(a["X-Workspace-ID"])
    client.portal.call(execution_worker.run_once, wid)
    assert get_message(client, a, reviewed)["state"] == "reconciling"
    boundaries["mode"] = "success"
    path = f"/api/v1/mailbox-webhooks/resend/{wid}/{integration['id']}/{data['sender']['id']}"
    original = boundaries["sent"]["text"]
    boundaries["sent"]["text"] = "Not the approved body"
    assert send_event(client, path, kind="email.sent").status_code == 409
    assert get_message(client, a, reviewed)["state"] == "reconciling"
    boundaries["sent"]["text"] = original
    assert send_event(client, path, kind="email.sent").status_code == 202
    assert send_event(client, path, kind="email.sent").status_code == 202
    assert get_message(client, a, reviewed)["state"] == "sent"
    expire(client, a)
    client.portal.call(execution_worker.run_once, wid)
    assert len([c for c in boundaries["calls"] if c[0] == "POST"]) == 1
    boundaries["reply_to"] = "<synthetic-rfc-id@example.com>"
    boundaries["body"] = "Sounds good, tell me more."
    incoming = send_event(client, path, event_id="reply-event")
    assert incoming.status_code == 202, incoming.text
    saved = client.get("/api/v1/inbox/messages/" + incoming.json()["inbound_message_id"], headers=a).json()
    assert saved["association"] == "linked" and saved["outbound_message_id"] == reviewed["message"]["id"]


def test_resend_reconnection_invalidates_existing_delivery_approval(client, fake_research, boundaries, monkeypatch):
    a, data, integration = prepare_resend(client, fake_research, boundaries)
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    changed = client.put("/api/v1/integrations/" + integration["id"], headers=a,
        json={"credentials": {"api_key": "rotated-synthetic-key-only", "webhook_secret": SECRET}})
    assert changed.status_code == 200
    assert client.post("/api/v1/integrations/" + integration["id"] + "/test", headers=a).status_code == 200
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    client.portal.call(execution_worker.run_once, UUID(a["X-Workspace-ID"]))
    assert get_message(client, a, reviewed)["state"] != "sent"
    assert not any(method == "POST" for method, _, _ in boundaries["calls"])


def test_resend_rate_limit_never_replays_after_idempotency_window(client, fake_research, boundaries, monkeypatch):
    a, data, _ = prepare_resend(client, fake_research, boundaries)
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    boundaries["mode"] = "rate_limited"
    wid = UUID(a["X-Workspace-ID"])
    client.portal.call(execution_worker.run_once, wid)
    async def expire_window():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=wid, workspace_role="owner")
            message = await db.get(Message, UUID(reviewed["message"]["id"]))
            message.attempted_at = datetime.utcnow() - timedelta(hours=24)
            await db.commit()
    client.portal.call(expire_window)
    boundaries["mode"] = "success"
    expire(client, a)
    client.portal.call(execution_worker.run_once, wid)
    assert get_message(client, a, reviewed)["error_code"] == "delivery_reconciliation_required"
    assert len([c for c in boundaries["calls"] if c[0] == "POST"]) == 1


@pytest.mark.parametrize("provider_id", [None, "", "not-a-uuid", EMAIL_ID])
def test_transport_requires_valid_explicit_provider_receipt(boundaries, monkeypatch, provider_id):
    from types import SimpleNamespace
    from backend.mail_transport import ResendTransport
    import asyncio
    async def reply(*args, **kwargs): return {"id": provider_id}
    monkeypatch.setattr(providers, "provider_request", reply)
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    adapter = ResendTransport(SimpleNamespace(config={"from_email": "sender@example.com"}), {"api_key": "test-only"}, SimpleNamespace(attempted_at=None))
    envelope = {"sender": "sender@example.com", "recipient": "jane@example.com", "subject": "Test", "body": "Synthetic"}
    if provider_id == EMAIL_ID:
        assert asyncio.run(adapter.send("workspace:" + EMAIL_ID, envelope)) == {"status": "accepted", "id": EMAIL_ID}
    else:
        with pytest.raises(providers.ProviderError, match="invalid_delivery_receipt"):
            asyncio.run(adapter.send("workspace:" + EMAIL_ID, envelope))


def test_send_auth_failure_persists_reconnect_and_safe_audit(client, fake_research, boundaries, monkeypatch):
    a, data, integration = prepare_resend(client, fake_research, boundaries)
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    monkeypatch.setattr(settings, "OUTBOUND_EMAIL_ENABLED", True)
    boundaries["mode"] = "reconnect_required"
    client.portal.call(execution_worker.run_once, UUID(a["X-Workspace-ID"]))
    row = client.get("/api/v1/integrations/" + integration["id"], headers=a).json()
    assert row["reconnect_required"] and row["health"] == "reconnect_required" and row["status"] == "error"
    assert get_message(client, a, reviewed)["state"] == "reconciling"
    audit = client.get("/api/v1/integrations/" + integration["id"] + "/audit", headers=a)
    assert audit.json()[0]["action"] == "mail_dispatch_failed"
    assert "synthetic-token-only" not in audit.text and SECRET not in audit.text


def test_reconnect_before_approval_requires_new_draft_and_review(client, fake_research, boundaries):
    a, data, integration = prepare_resend(client, fake_research, boundaries)
    old = data["draft"]
    changed = client.put("/api/v1/integrations/" + integration["id"], headers=a,
        json={"credentials": {"api_key": "rotated-synthetic-only", "webhook_secret": SECRET}})
    assert changed.status_code == 200
    submitted = post(client, a, "/drafts/" + old["id"] + "/submit",
        {"content_hash": old["content_hash"], "expected_revision": 1})
    stale_approval = client.post("/api/v1/outreach/drafts/" + old["id"] + "/approve", headers=a,
        json={"content_hash": old["content_hash"], "reviewed": True, "expected_revision": submitted["revision"]})
    assert stale_approval.status_code == 409
    fresh = post(client, a, "/scheduled/" + old["scheduled_id"] + "/drafts", {})
    assert fresh["id"] != old["id"]
    assert fresh["content_hash"] != old["content_hash"]
    repeated = post(client, a, "/scheduled/" + old["scheduled_id"] + "/drafts", {})
    assert repeated["id"] == fresh["id"]
    assert not any(method == "POST" for method, _, _ in boundaries["calls"])


    state = client.get("/api/v1/outreach/drafts/" + fresh["id"] + "/review", headers=a).json()
    assert state["status"] == "draft"
    assert len(state["history"]) == 3
    stale = client.post("/api/v1/outreach/drafts/" + old["id"] + "/submit", headers=a,
        json={"content_hash": old["content_hash"], "expected_revision": 1})
    assert stale.status_code == 409
    data["draft"] = fresh
    assert approve_draft(client, a, data)["message"]["draft_id"] == fresh["id"]
