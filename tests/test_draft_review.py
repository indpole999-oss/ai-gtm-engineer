"""Synthetic fixtures only; no live research, AI, or delivery provider calls."""
from uuid import UUID
import pytest
from sqlalchemy import select, func
from fastapi import HTTPException
from backend.database import AsyncSessionLocal, WorkspaceMembership
from backend.outreach_models import DraftReviewEvent, MessageDraft, Message
from backend.planning_models import ActionCommand, ExecutionCycle
from backend import execution_worker as worker
from test_outreach import setup_outreach, post, BASE, provider  # noqa: F401
from test_research import fake_research  # noqa: F401
from test_workspace_security import signup


def review(client, headers, draft):
    result = client.get(BASE + f"/drafts/{draft['id']}/review", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def inputs(draft, state):
    return {"content_hash": draft["content_hash"], "expected_revision": state["revision"]}


def change_role(client, headers, role):
    async def run():
        async with AsyncSessionLocal() as db:
            row = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(headers["X-Workspace-ID"])))
            row.role = role
            await db.commit()
    client.portal.call(run)


def test_complete_review_journey_revisions_decisions_audit_and_no_send(client, fake_research, provider):
    a, data = setup_outreach(client, fake_research)
    original = draft = data["draft"]
    first = review(client, a, draft)
    assert first["status"] == "draft" and first["evidence"]["excerpt"] in draft["envelope"]["body"]
    assert first["evidence"]["source_hash"]
    # Duplicate generation retrieves the same persisted snapshot.
    assert post(client, a, f"/scheduled/{data['scheduled']['id']}/drafts")["id"] == draft["id"]
    for decision in ("changes_requested", "rejected"):
        state = review(client, a, draft)
        submit_body = inputs(draft, state)
        submitted = post(client, a, f"/drafts/{draft['id']}/submit", submit_body)
        assert post(client, a, f"/drafts/{draft['id']}/submit", submit_body)["revision"] == submitted["revision"]
        decision_body = {**inputs(draft, submitted), "action": decision, "reason": "Please adjust the introduction"}
        decided = post(client, a, f"/drafts/{draft['id']}/decision", decision_body)
        assert decided["status"] == decision
        assert post(client, a, f"/drafts/{draft['id']}/decision", decision_body)["revision"] == decided["revision"]
        edit_body = {**inputs(draft, decided), "subject": draft["envelope"]["subject"] + "?", "body": draft["envelope"]["body"]}
        updated = post(client, a, f"/drafts/{draft['id']}/revisions", edit_body)
        assert post(client, a, f"/drafts/{draft['id']}/revisions", edit_body)["id"] == updated["id"]
        assert updated["id"] != draft["id"]
        assert client.post(BASE + f"/drafts/{draft['id']}/submit", headers=a, json=inputs(draft, decided)).status_code == 409
        draft = updated
    state = review(client, a, draft)
    assert state["warnings"]
    submitted = post(client, a, f"/drafts/{draft['id']}/submit", inputs(draft, state))
    approval = {**inputs(draft, submitted), "reviewed": True}
    assert client.post(BASE + f"/drafts/{draft['id']}/approve", headers=a, json=approval).status_code == 409
    approval["acknowledge_unverified_edits"] = True
    accepted = post(client, a, f"/drafts/{draft['id']}/approve", approval)
    assert accepted["plan"]["status"] == "draft"
    assert post(client, a, f"/drafts/{draft['id']}/approve", approval)["message"]["id"] == accepted["message"]["id"]
    assert review(client, a, draft)["status"] == "approved"
    assert len([event for event in review(client, a, draft)["history"] if event["action"] == "approved"]) == 1
    assert client.get(BASE + f"/drafts/{original['id']}", headers=a).json()["envelope"] == original["envelope"]
    assert len(client.get(BASE + "/drafts", headers=a).json()) == 3
    assert len(client.get(BASE + "/review-queue", headers=a).json()) == 1
    assert provider.calls == 0
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    async def counts():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            return [await db.scalar(select(func.count()).select_from(model)) for model in (Message, ActionCommand, ExecutionCycle)]
    assert client.portal.call(counts) == [1, 0, 0]


def test_prospect_retrieval_is_grounded_and_idempotent(client, fake_research, provider):
    a, data = setup_outreach(client, fake_research)
    enrollment = data["enrollment"]
    contact = enrollment["contact_id"]
    eligible = client.get(BASE + f"/prospects/{contact}/eligibility", headers=a).json()
    assert eligible[0]["id"] == enrollment["research_job_id"]
    body = {key: enrollment[key] for key in ("version_id", "sender_id", "research_job_id")}
    for _ in range(2):
        assert post(client, a, f"/prospects/{contact}/draft", body)["id"] == data["draft"]["id"]
    for resource in ("enrollments", "scheduled", "drafts"):
        assert len(client.get(BASE + "/" + resource, headers=a).json()) == 1
    assert provider.calls == 0


def test_prospect_new_sequence_creates_exactly_one_atomic_draft(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    version = post(client, a, f"/sequences/{data['sequence']['id']}/versions", {"steps": [{"delay_seconds": 0, "purpose": "Synthetic new step"}]})
    enrollment = data["enrollment"]
    body = {key: enrollment[key] for key in ("sender_id", "research_job_id")}
    body["version_id"] = version["id"]
    path = f"/prospects/{enrollment['contact_id']}/draft"
    first = post(client, a, path, body)
    assert post(client, a, path, body)["id"] == first["id"]
    assert len(client.get(BASE + "/enrollments", headers=a).json()) == 2
    assert len(client.get(BASE + "/drafts", headers=a).json()) == 2


@pytest.mark.parametrize("change", ["unknown_fit", "unsupported_buyer"])
def test_unqualified_prospect_rejected_without_customer_draft(client, fake_research, change):
    # Research fixtures are test-only, and acceptance still uses the real service.
    if change == "unknown_fit":
        fake_research["fit"] = "unknown"
    else:
        fake_research["buyers"] = []
    a, data = setup_outreach(client, fake_research, compose_draft=False)
    assert client.post(BASE + f"/scheduled/{data['scheduled']['id']}/drafts", headers=a).status_code == 409
    assert client.get(BASE + "/drafts", headers=a).json() == []
    assert client.get(BASE + f"/prospects/{data['enrollment']['contact_id']}/eligibility", headers=a).json() == []


def test_edits_cannot_remove_grounding_or_inject_prohibited_claim(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    draft = data["draft"]
    state = review(client, a, draft)
    body = {**inputs(draft, state), "subject": "Synthetic edit", "body": "Unsupported invented claims"}
    response = client.post(BASE + f"/drafts/{draft['id']}/revisions", headers=a, json=body)
    assert response.status_code == 409 and "intact" in response.text
    assert len(client.get(BASE + "/drafts", headers=a).json()) == 1
    body["body"] = draft["envelope"]["body"] + "\nWe grew 999 percent."
    edited = post(client, a, f"/drafts/{draft['id']}/revisions", body)
    assert review(client, a, edited)["warnings"]


@pytest.mark.parametrize("role", ["viewer", "member"])
def test_review_permissions_enforced_for_all_actions(client, fake_research, role):
    a, data = setup_outreach(client, fake_research)
    draft = data["draft"]
    state = review(client, a, draft)
    submitted = post(client, a, f"/drafts/{draft['id']}/submit", inputs(draft, state))
    change_role(client, a, role)
    for action in ("rejected", "changes_requested"):
        assert client.post(BASE + f"/drafts/{draft['id']}/decision", headers=a,
            json={**inputs(draft, submitted), "action": action, "reason": "Synthetic feedback"}).status_code == 403
    assert client.post(BASE + f"/drafts/{draft['id']}/approve", headers=a,
        json={**inputs(draft, submitted), "reviewed": True}).status_code == 403
    if role == "viewer":
        assert client.post(BASE + f"/drafts/{draft['id']}/submit", headers=a, json=inputs(draft, state)).status_code == 403
        assert client.post(BASE + f"/drafts/{draft['id']}/revisions", headers=a,
            json={**inputs(draft, state), "subject": "Edit", "body": draft["envelope"]["body"]}).status_code == 403


def test_member_can_edit_and_submit_but_never_approve(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    draft = data["draft"]
    state = review(client, a, draft)
    change_role(client, a, "member")
    edited = post(client, a, f"/drafts/{draft['id']}/revisions",
        {**inputs(draft, state), "subject": "Synthetic subject", "body": draft["envelope"]["body"]})
    assert post(client, a, f"/drafts/{edited['id']}/submit", inputs(edited, review(client, a, edited)))["status"] == "submitted"


def test_cross_workspace_queue_history_mutations_and_prospect_are_hidden(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    b = signup(client, "review-other@example.com")
    draft = data["draft"]
    assert client.get(BASE + "/review-queue", headers=b).json() == []
    assert client.get(BASE + f"/drafts/{draft['id']}/review", headers=b).status_code == 404
    body = inputs(draft, review(client, a, draft))
    for suffix, payload in (("submit", body), ("revisions", {**body, "subject": "x", "body": "x"}),
        ("decision", {**body, "action": "rejected", "reason": "x"}),
        ("approve", {**body, "reviewed": True})):
        assert client.post(BASE + f"/drafts/{draft['id']}/{suffix}", headers=b, json=payload).status_code == 404
    contact = data["enrollment"]["contact_id"]
    assert client.get(BASE + f"/prospects/{contact}/eligibility", headers=b).status_code == 404
    payload = {key: data["enrollment"][key] for key in ("version_id", "sender_id", "research_job_id")}
    assert client.post(BASE + f"/prospects/{contact}/draft", headers=b, json=payload).status_code == 404
    assert client.get(BASE + "/review-queue").status_code == 401


def test_stale_duplicate_conflicting_and_invalid_actions_fail_closed(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    draft = data["draft"]
    state = review(client, a, draft)
    body = inputs(draft, state)
    assert client.post(BASE + f"/drafts/{draft['id']}/approve", headers=a, json={**body, "reviewed": True}).status_code == 409
    assert client.post(BASE + f"/drafts/{draft['id']}/submit", headers=a, json={**body, "content_hash": "0" * 64}).status_code == 409
    submitted = post(client, a, f"/drafts/{draft['id']}/submit", body)
    assert client.post(BASE + f"/drafts/{draft['id']}/decision", headers=a,
        json={**body, "action": "rejected", "reason": "Stale"}).status_code == 409
    assert client.post(BASE + f"/drafts/{draft['id']}/revisions", headers=a,
        json={**inputs(draft, submitted), "subject": "Editing submitted", "body": draft["envelope"]["body"]}).status_code == 409
    assert client.post(BASE + f"/drafts/{draft['id']}/decision", headers=a,
        json={**inputs(draft, submitted), "action": "rejected", "reason": "   "}).status_code == 422
    post(client, a, f"/drafts/{draft['id']}/decision", {**inputs(draft, submitted), "action": "rejected", "reason": "Not ready"})
    assert client.post(BASE + f"/drafts/{draft['id']}/approve", headers=a,
        json={**inputs(draft, submitted), "reviewed": True}).status_code == 409


def test_review_audit_is_immutable(client, fake_research):
    a, data = setup_outreach(client, fake_research)
    async def mutate():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            event = await db.scalar(select(DraftReviewEvent))
            event.reason = "Tampered"
            with pytest.raises(HTTPException, match="immutable"):
                await db.commit()
    client.portal.call(mutate)


def test_rejected_source_claim_blocks_submission_and_approval(client, fake_research):
    from backend.research_models import ClaimVerification
    a, data = setup_outreach(client, fake_research)
    draft = data["draft"]
    async def reject_claim():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            db.add(ClaimVerification(claim_id=UUID(draft["envelope"]["research_claim_id"]),
                user_id=UUID(draft["created_by"]), decision="rejected", reason="Synthetic review rejection"))
            await db.commit()
    state = review(client, a, draft)
    submitted = post(client, a, f"/drafts/{draft['id']}/submit", inputs(draft, state))
    client.portal.call(reject_claim)
    result = client.post(BASE + f"/drafts/{draft['id']}/approve", headers=a,
        json={**inputs(draft, submitted), "reviewed": True})
    assert result.status_code == 409 and "rejected" in result.text
    assert client.get(BASE + "/messages", headers=a).json() == []
