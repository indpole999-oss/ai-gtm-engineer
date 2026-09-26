"""Deterministic, offline inbox/worker contracts and outreach safety boundaries."""
from datetime import datetime, timedelta
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from backend import inbox_service as service, inbox_worker, execution_worker as worker
from backend.database import AsyncSessionLocal, engine, WorkspaceMembership, Meeting, CRMRecord
from backend.planning_models import OutboxEvent, DomainEvent, ActionCommand
from backend.inbox_models import InboundMessage, ReplyClassification, InboxPause, InboundReceipt
from backend.inbox_classifier import classify
from backend.outreach_models import Enrollment, Message
from test_outreach import ready, setup_outreach, provider, fake_research, post, approve_draft, get_message  # noqa: F401
from test_planning_execution import approve
from test_workspace_security import signup

BASE = "/api/v1/inbox"


def sent(client, fake_research, provider):
    a, data, reviewed, cycle = ready(client, fake_research)
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    return a, data, get_message(client, a, reviewed)


def event(outbound=None, **changes):
    return {"provider_event_id": "event-1", "provider_message_id": "reply-1", "provider_thread_id": "thread-1",
        "in_reply_to": outbound["provider_message_id"] if outbound else None,
        "sender_email": "jane@example.com", "recipient_email": "sender@example.com", "subject": "Re: Question",
        "body": "Sounds good, tell me more.", **changes}


def ingest(client, a, data, body):
    result = client.post(BASE + "/simulated-events/" + data["sender"]["id"], headers=a, json=body)
    assert result.status_code == 202, result.text
    return result.json()


def detail(client, a, message):
    result = client.get(BASE + "/messages/" + message["id"], headers=a)
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize("body,category", [
    ("Sounds good, tell me more.", "positive"), ("Not interested, no thanks.", "negative"),
    ("It is too expensive for us.", "objection"), ("I am out of office until Monday.", "out_of_office"),
    ("You have the wrong person.", "wrong_person"), ("How does it work?", "question"),
    ("Let's schedule a meeting.", "meeting_intent"), ("Please unsubscribe me.", "unsubscribe"),
    ("Perhaps later, who knows.", "other"), ("Sounds good but too expensive.", "other"),
])
def test_classification_rules(body, category):
    result = classify("Re: Question", body)
    assert result.category == category
    assert result.reason and result.classifier_version and result.recommended_action
    if category == "other":
        assert result.confidence is None and result.requires_review


def test_quoted_opt_out_footer_is_not_an_unsubscribe():
    assert classify("Re: Question", "Sounds good!\n\nOn Tuesday someone wrote:\nTo opt out, reply unsubscribe.").category == "positive"
    assert classify("Re: Question", "Sounds good!\n> To opt out, reply unsubscribe.").category == "positive"
    assert classify("Notice", "Delivery diagnostic", "auto-generated").category == "other"
    assert classify("Reply", "Please do not unsubscribe me").category == "other"
    assert classify("Reply", "To opt out, reply unsubscribe.").category == "other"


def test_persistence_linkage_classification_and_draft_only(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound, body="Let's schedule a meeting."))
    assert incoming["association"] == "linked"
    for field in ("contact_id", "company_id", "campaign_id", "sequence_id", "sequence_version_id", "brain_version_id", "research_job_id"):
        assert incoming[field] == data["draft"]["envelope"][field]
    assert incoming["outbound_message_id"] == outbound["id"]
    assert incoming["enrollment_id"] == data["enrollment"]["id"]
    assert incoming["processing"]["status"] == "pending"
    assert incoming["classification"] is None
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    current = detail(client, a, incoming)
    assert current["classification"]["category"] == "meeting_intent"
    assert current["processing"]["status"] == "processed"
    draft = client.post(BASE + "/messages/" + incoming["id"] + "/suggested-reply", headers=a)
    assert draft.status_code == 201, draft.text
    draft = draft.json()
    assert draft["status"] == "draft" and draft["inbound_message_id"] == incoming["id"]
    assert draft["context"]["prior_outreach"]["brain_version_id"] == incoming["brain_version_id"]
    assert client.post(BASE + "/messages/" + incoming["id"] + "/suggested-reply", headers=a).json()["id"] == draft["id"]
    thread = client.get(BASE + "/threads/" + incoming["thread_id"], headers=a).json()
    assert thread["messages"][0]["id"] == incoming["id"] and thread["outbound_messages"][0]["id"] == outbound["id"]
    async def no_phase8():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            assert await db.scalar(select(func.count(Meeting.id))) == 0
            assert await db.scalar(select(func.count(CRMRecord.id))) == 0
            assert await db.scalar(select(func.count(Message.id))) == 1
    client.portal.call(no_phase8)
    assert provider.calls == 1


def test_duplicate_event_and_message_have_one_set_of_side_effects(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    first = ingest(client, a, data, event(outbound, body="Please unsubscribe me"))
    again = ingest(client, a, data, event(outbound, body="Please unsubscribe me"))
    another = ingest(client, a, data, event(outbound, body="Please unsubscribe me", provider_event_id="event-2"))
    assert first["id"] == again["id"] == another["id"]
    assert first["suppressed"] and len(first["sequence_holds"]) == 1
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    async def counts():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            for model, count in [(InboundMessage, 1), (InboundReceipt, 2), (ReplyClassification, 1), (InboxPause, 1)]:
                assert await db.scalar(select(func.count(model.id))) == count
            for kind in ("inbound_received", "inbound_sequence_held", "inbound_unsubscribe_suppressed", "inbound_classified"):
                assert await db.scalar(select(func.count(DomainEvent.id)).where(DomainEvent.kind == kind)) == 1
    client.portal.call(counts)
    assert client.post(BASE + "/simulated-events/" + data["sender"]["id"], headers=a, json=event(outbound, body="Tampered payload")).status_code == 409


@pytest.mark.parametrize("body", ["Sounds good", "Please unsubscribe me"])
@pytest.mark.parametrize("already_claimed", [False, True])
def test_pending_approved_outreach_blocked_immediately_before_classification(client, fake_research, provider, body, already_claimed):
    a, data = setup_outreach(client, fake_research, steps=[{"delay_seconds": 0, "purpose": "First"}, {"delay_seconds": 0, "purpose": "Second"}])
    wid = UUID(a["X-Workspace-ID"])
    first_step = next(s for s in client.get("/api/v1/outreach/steps", headers=a).json() if s["position"] == 0)
    data["scheduled"] = next(s for s in client.get("/api/v1/outreach/scheduled", headers=a).json() if s["sequence_step_id"] == first_step["id"])
    data["draft"] = post(client, a, f"/scheduled/{data['scheduled']['id']}/drafts")
    reviewed = approve_draft(client, a, data)
    approve(client, a, reviewed["plan"])
    client.portal.call(worker.run_once, wid)
    outbound = get_message(client, a, reviewed)
    assert outbound["state"] == "sent", outbound
    later = next(s for s in client.get("/api/v1/outreach/scheduled", headers=a).json() if s["id"] != data["scheduled"]["id"])
    later_data = {**data, "draft": post(client, a, f"/scheduled/{later['id']}/drafts")}
    later_reviewed = approve_draft(client, a, later_data)
    later_cycle = approve(client, a, later_reviewed["plan"])
    claim = client.portal.call(worker.claim_next, wid) if already_claimed else None
    if already_claimed:
        assert claim
    incoming = ingest(client, a, data, event(outbound, body=body))
    assert incoming["processing"]["status"] == "pending"
    assert client.get("/api/v1/outreach/enrollments/" + data["enrollment"]["id"], headers=a).json()["status"] == "paused"
    assert not client.portal.call(worker.claim_next, wid)
    if claim:
        with pytest.raises(HTTPException):
            client.portal.call(worker.perform, wid, claim)
        client.portal.call(worker.finish, wid, claim, None, "reply_hold")
    assert client.post("/api/v1/outreach/enrollments/" + data["enrollment"]["id"] + "/control", headers=a, json={"status": "active"}).status_code == 409
    async def protected_even_if_status_changed():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            e = await db.scalar(select(Enrollment).where(Enrollment.id == UUID(data["enrollment"]["id"])))
            e.status = "active"
            await db.commit()
    client.portal.call(protected_even_if_status_changed)
    client.portal.call(engine.dispose)
    client.portal.call(worker.run_once, wid)  # Consume classification only.
    assert not client.portal.call(worker.claim_next, wid)
    state = client.get("/api/v1/gtm/cycles/" + later_cycle["id"], headers=a).json()
    assert state["commands"][0]["attempts"] == int(already_claimed)
    assert get_message(client, a, later_reviewed)["state"] == "approved"
    if body.startswith("Please"):
        assert incoming["suppressed"]
    assert provider.calls == 1


def test_unassociated_and_wrong_sender_do_not_invent_contact(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    unknown = ingest(client, a, data, event(None, in_reply_to="unknown-provider-id"))
    assert unknown["association"] == "unassociated" and unknown["contact_id"] is None and unknown["enrollment_id"] is None
    mismatch = ingest(client, a, data, event(outbound, provider_event_id="event-2", provider_message_id="reply-2", sender_email="different@example.com"))
    assert mismatch["association"] == "sender_mismatch" and mismatch["outbound_message_id"] is None
    assert client.get("/api/v1/outreach/enrollments/" + data["enrollment"]["id"], headers=a).json()["status"] == "active"


def test_thread_reference_is_supported_linkage_and_ooo_is_distinct(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    first = ingest(client, a, data, event(outbound, body="I am out of office", auto_submitted="auto-replied"))
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    first = detail(client, a, first)
    assert first["classification"]["category"] == "out_of_office"
    assert first["sequence_holds"][0]["reason"] == "out_of_office"
    second = ingest(client, a, data, event(None, provider_event_id="event-2", provider_message_id="reply-2"))
    assert second["thread_id"] == first["thread_id"] and second["outbound_message_id"] == outbound["id"]


def test_manual_override_is_append_only_and_never_removes_suppression(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound, body="Not sure yet"))
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    path = BASE + "/messages/" + incoming["id"] + "/override"
    override = {"category": "unsubscribe", "reason": "Reviewed the reply and confirmed opt-out", "expected_number": 1, "reviewed": True}
    assert client.post(path, headers=a, json=override).status_code == 201
    assert client.post(path, headers=a, json=override).status_code == 409
    override.update(category="positive", expected_number=2)
    assert client.post(path, headers=a, json=override).status_code == 201
    current = detail(client, a, incoming)
    assert len(current["classification_history"]) == 3
    assert current["classification"]["manual_override"] and current["classification"]["overridden_by"]
    assert current["suppressed"]
    assert client.post(BASE + "/messages/" + incoming["id"] + "/suggested-reply", headers=a).status_code == 409


def test_cross_workspace_direct_access_and_event_identity(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound))
    b = signup(client, "inbox-other@example.com")
    assert client.get(BASE + "/threads", headers=b).json() == []
    for path in ("/threads/" + incoming["thread_id"], "/messages/" + incoming["id"]):
        assert client.get(BASE + path, headers=b).status_code == 404
    assert client.post(BASE + "/simulated-events/" + data["sender"]["id"], headers=b, json=event(outbound)).status_code == 404
    assert client.post(BASE + "/messages/" + incoming["id"] + "/suggested-reply", headers=b).status_code == 404


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_inbox_rbac(client, fake_research, provider, role):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound))
    async def change_role():
        async with AsyncSessionLocal() as db:
            row = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            row.role = role
            await db.commit()
    client.portal.call(change_role)
    assert client.get(BASE + "/messages/" + incoming["id"], headers=a).status_code == 200
    assert client.post(BASE + "/simulated-events/" + data["sender"]["id"], headers=a, json=event(outbound)).status_code == 403
    assert client.post(BASE + "/messages/" + incoming["id"] + "/override", headers=a, json={"category": "positive", "reason": "Reviewed inbound message", "expected_number": 0, "reviewed": True}).status_code == 403


def test_restart_expired_lease_and_stale_completion(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound))
    wid = UUID(a["X-Workspace-ID"])
    first = client.portal.call(inbox_worker.claim_next, wid)
    assert first and not client.portal.call(inbox_worker.claim_next, wid)
    async def expire():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            work = await db.scalar(select(OutboxEvent).where(OutboxEvent.id == first["id"]))
            work.lease_until = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire)
    client.portal.call(engine.dispose)
    second = client.portal.call(inbox_worker.claim_next, wid)
    assert second["token"] != first["token"]
    assert not client.portal.call(inbox_worker.perform, wid, first)
    assert client.portal.call(inbox_worker.perform, wid, second)
    assert not client.portal.call(inbox_worker.perform, wid, second)
    assert detail(client, a, incoming)["processing"]["status"] == "processed"
    assert len(detail(client, a, incoming)["classification_history"]) == 1
    assert provider.calls == 1


def test_manual_review_before_worker_wins(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound))
    r = client.post(BASE + "/messages/" + incoming["id"] + "/override", headers=a,
        json={"category": "question", "reason": "Customer has a specific question", "expected_number": 0, "reviewed": True})
    assert r.status_code == 201, r.text
    client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    current = detail(client, a, incoming)
    assert len(current["classification_history"]) == 1 and current["classification"]["category"] == "question"


def test_same_provider_ids_are_mailbox_scoped_and_input_cannot_select_workspace(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    first = ingest(client, a, data, event(outbound))
    b = signup(client, "inbox-namespace@example.com")
    sender = post(client, b, "/senders", {"email": "sender@example.com", "provider": "fake"})
    second = ingest(client, b, {"sender": sender}, event(outbound))
    assert second["id"] != first["id"] and second["association"] == "unassociated"
    assert second["outbound_message_id"] is None and second["contact_id"] is None
    path = BASE + "/simulated-events/" + data["sender"]["id"]
    assert client.post(path, json=event(outbound)).status_code == 401
    assert client.post(path, headers=a, json=event(outbound, workspace_id=b["X-Workspace-ID"])).status_code == 422
    assert client.post(path, headers=a, json=event(outbound, recipient_email="other@example.com")).status_code == 409


def test_unassociated_opt_out_suppresses_without_fabricating_linkage(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(None, body="unsubscribe"))
    assert incoming["association"] == "unassociated" and incoming["contact_id"] is None
    assert incoming["suppressed"] and incoming["sequence_holds"] == []


def test_failed_processing_retries_atomically_without_losing_safety(client, fake_research, provider, monkeypatch):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound, body="unsubscribe"))
    wid = UUID(a["X-Workspace-ID"])
    original = service.classify_message
    async def fail_after_write(db, message):
        await original(db, message)
        raise RuntimeError("Simulated crash before transaction acknowledgement")
    monkeypatch.setattr(service, "classify_message", fail_after_write)
    async def due():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            work = await db.scalar(select(OutboxEvent).join(DomainEvent, DomainEvent.id == OutboxEvent.event_id).where(DomainEvent.kind == "inbound_received"))
            work.due_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    for _ in range(3):
        client.portal.call(due)
        client.portal.call(worker.run_once, wid)
        current = detail(client, a, incoming)
        assert current["classification"] is None and current["suppressed"]
        assert len(current["sequence_holds"]) == 1
    assert current["processing"]["status"] == "failed"
    monkeypatch.setattr(service, "classify_message", original)
    assert client.post(BASE + "/messages/" + incoming["id"] + "/retry-classification", headers=a).status_code == 200
    client.portal.call(engine.dispose)
    client.portal.call(worker.run_once, wid)
    assert detail(client, a, incoming)["classification"]["category"] == "unsubscribe"
    assert len(detail(client, a, incoming)["classification_history"]) == 1
    assert provider.calls == 1


def test_unsubscribe_arriving_at_dispatch_commit_gap_blocks_send(client, fake_research, provider, monkeypatch):
    from backend import outreach_service
    a, data, reviewed, cycle = ready(client, fake_research)
    wid = UUID(a["X-Workspace-ID"])
    original = outreach_service.lock_workspace
    calls = 0
    async def interleaved(db):
        nonlocal calls
        calls += 1
        if calls == 2:
            async with AsyncSessionLocal() as incoming_db:
                worker.bind(incoming_db, wid)
                await service.ingest(incoming_db, UUID(data["sender"]["id"]), service.InboundEvent(**event(None, body="Unsubscribe")))
        await original(db)
    monkeypatch.setattr(outreach_service, "lock_workspace", interleaved)
    client.portal.call(worker.run_once, wid)
    assert calls == 2 and provider.calls == 0
    assert get_message(client, a, reviewed)["state"] != "sent"
    assert client.get("/api/v1/outreach/suppressions", headers=a).json()[0]["reason"] == "unsubscribe"


def test_reply_to_inbound_reconstructs_only_explicit_same_mailbox_sender_chain(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    first = ingest(client, a, data, event(outbound, provider_thread_id=None))
    second = ingest(client, a, data, event(provider_event_id="event-2", provider_message_id="reply-2",
        provider_thread_id=None, in_reply_to=first["provider_message_id"], body="How does it work?"))
    assert second["thread_id"] == first["thread_id"]
    assert second["outbound_message_id"] == outbound["id"] and second["association"] == "linked"
    unknown = ingest(client, a, data, event(provider_event_id="event-3", provider_message_id="reply-3",
        provider_thread_id=None, in_reply_to=first["provider_message_id"], sender_email="stranger@example.com"))
    assert unknown["thread_id"] != first["thread_id"] and unknown["outbound_message_id"] is None
    thread = client.get(BASE + "/threads/" + first["thread_id"], headers=a).json()
    assert {m["id"] for m in thread["messages"]} == {first["id"], second["id"]}
    assert len(thread["outbound_messages"]) == 1 and provider.calls == 1
