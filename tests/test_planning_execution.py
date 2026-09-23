from datetime import datetime, timedelta
from uuid import UUID
import pytest
from sqlalchemy import select
from backend.database import AsyncSessionLocal, WorkspaceMembership
from backend.planning_models import ActionCommand
from backend import planning_service
from backend import execution_worker as worker
from test_workspace_security import signup, company
from test_research import published, fake_research  # noqa: F401


def proposal(client, headers):
    brain, account = published(client, headers), company(client, headers)
    goal = client.post("/api/v1/gtm/goals", headers=headers, json={"objective": "Research evidence of fit for this company", "brain_version_id": brain["id"], "targets": [{"company_id": account["id"], "source_urls": ["https://example.com/"]}]})
    assert goal.status_code == 201, goal.text
    plan = client.post(f"/api/v1/gtm/goals/{goal.json()['id']}/plans", headers=headers, json={"mode": "research_template"})
    assert plan.status_code == 201, plan.text
    return plan.json()


def approve(client, headers, plan):
    response = client.post(f"/api/v1/gtm/plans/{plan['id']}/approve", headers=headers, json={"content_hash": plan["content_hash"], "reviewed": True})
    assert response.status_code == 201, response.text
    return response.json()


def test_no_execution_before_approval_and_durable_completion(client, fake_research):
    a = signup(client, "planner@example.com")
    workspace_id = UUID(a["X-Workspace-ID"])
    plan = proposal(client, a)
    assert plan["author_method"] == "explicit_research_template"
    assert len(plan["document"]["brain_hash"]) == 64
    assert not client.portal.call(worker.run_once, workspace_id)
    wrong = client.post(f"/api/v1/gtm/plans/{plan['id']}/approve", headers=a, json={"content_hash": "0" * 64, "reviewed": True})
    assert wrong.status_code == 409
    cycle = approve(client, a, plan)
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/approve", headers=a, json={"content_hash": plan["content_hash"], "reviewed": True}).status_code == 409
    assert client.portal.call(worker.run_once, workspace_id)
    state = client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()
    assert state["status"] == "completed", state
    assert state["commands"][0]["attempts"] == 1
    assert state["steps"][0]["output"]["research_job_id"]
    assert not client.portal.call(worker.run_once, workspace_id)
    assert {e["kind"] for e in state["events"]} >= {"plan_approved", "command_claimed", "command_succeeded"}


def test_pause_resume_cancel_and_cross_tenant_access(client, fake_research):
    a, b = signup(client, "control-a@example.com"), signup(client, "control-b@example.com")
    plan = proposal(client, a)
    cycle = approve(client, a, plan)
    path = f"/api/v1/gtm/cycles/{cycle['id']}"
    assert client.get("/api/v1/gtm/goals", headers=b).json() == []
    assert client.get("/api/v1/gtm/cycles", headers=b).json() == []
    assert client.get(f"/api/v1/gtm/plans/{plan['id']}", headers=b).status_code == 404
    assert client.get(path, headers=b).status_code == 404
    assert client.post(path + "/control", headers=b, json={"action": "cancel"}).status_code == 404
    assert client.post(path + "/control", headers=a, json={"action": "pause"}).json()["status"] == "paused"
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert client.post(path + "/control", headers=a, json={"action": "resume"}).json()["status"] == "running"
    assert client.post(path + "/control", headers=a, json={"action": "cancel"}).json()["status"] == "cancelled"
    assert not client.portal.call(worker.run_once, UUID(a["X-Workspace-ID"]))
    assert client.post(path + "/control", headers=a, json={"action": "resume"}).status_code == 409


def test_expired_lease_recovery_and_stale_worker_cannot_acknowledge(client, fake_research):
    a = signup(client, "lease@example.com")
    wid = UUID(a["X-Workspace-ID"])
    cycle = approve(client, a, proposal(client, a))
    first = client.portal.call(worker.claim_next, wid)
    assert first and not client.portal.call(worker.claim_next, wid)
    async def expire():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            command = await db.scalar(select(ActionCommand).where(ActionCommand.id == first["id"]))
            command.lease_until = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire)
    second = client.portal.call(worker.claim_next, wid)
    assert second["token"] != first["token"]
    client.portal.call(worker.finish, wid, first, {"forged": True})
    state = client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()
    assert state["steps"][0]["status"] == "running" and state["steps"][0]["output"] is None
    result = client.portal.call(worker.perform, wid, second)
    client.portal.call(worker.finish, wid, second, result)
    assert client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()["status"] == "completed"


def test_revoked_approver_pauses_execution(client, fake_research):
    a = signup(client, "revoked-approval@example.com")
    wid = UUID(a["X-Workspace-ID"])
    cycle = approve(client, a, proposal(client, a))
    async def revoke():
        async with AsyncSessionLocal() as db:
            membership = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == wid))
            membership.role = "member"
            await db.commit()
    client.portal.call(revoke)
    assert not client.portal.call(worker.run_once, wid)
    state = client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()
    assert state["status"] == "paused" and state["stop_reason"] == "approval_no_longer_valid"


def test_bounded_retries_backoff_and_safe_failure(client, monkeypatch):
    a = signup(client, "retry@example.com")
    wid = UUID(a["X-Workspace-ID"])
    cycle = approve(client, a, proposal(client, a))
    async def fail(*args):
        raise TimeoutError("must-not-expose-provider-secret")
    monkeypatch.setattr(worker, "perform", fail)
    async def make_due():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            command = await db.scalar(select(ActionCommand))
            command.due_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    for attempt in range(3):
        assert client.portal.call(worker.run_once, wid)
        assert not client.portal.call(worker.run_once, wid)
        client.portal.call(make_due)
    state = client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a)
    assert state.json()["status"] == "failed"
    assert state.json()["commands"][0]["attempts"] == 3
    assert "must-not-expose" not in state.text


def test_command_payload_tampering_cannot_expand_approved_scope(client, fake_research):
    a = signup(client, "integrity@example.com")
    wid = UUID(a["X-Workspace-ID"])
    cycle = approve(client, a, proposal(client, a))
    async def tamper():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            command = await db.scalar(select(ActionCommand))
            command.payload = {**command.payload, "target": {**command.payload["target"], "source_urls": ["https://unapproved.example/"]}}
            await db.commit()
    client.portal.call(tamper)
    assert not client.portal.call(worker.run_once, wid)
    state = client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()
    assert state["status"] == "paused" and state["stop_reason"] == "command_integrity_failed"


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_approval_requires_owner_or_admin(client, role):
    a = signup(client, f"approve-{role}@example.com")
    plan = proposal(client, a)
    async def change_role():
        async with AsyncSessionLocal() as db:
            membership = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            membership.role = role
            await db.commit()
    client.portal.call(change_role)
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/approve", headers=a, json={"content_hash": plan["content_hash"], "reviewed": True}).status_code == 403


def test_local_planner_contract_and_invalid_graph_rejection(client, monkeypatch):
    a = signup(client, "ai-plan@example.com")
    original = proposal(client, a)
    class FakePlanner:
        async def plan(self, context):
            assert context["company_brain"]["icp"] == "Customer-reviewed icp"
            assert context["workspace_policy"]["paid_budget_cents"] == 0
            assert "integrations" in context and "pipeline_state" in context and "historical_outcomes" in context
            return planning_service.PlanDocument.model_validate(original["document"]["plan"]), "deterministic-test-planner"
    monkeypatch.setattr(planning_service, "planner_provider", FakePlanner)
    response = client.post(f"/api/v1/gtm/goals/{original['goal_id']}/plans", headers=a, json={"mode": "local_ai"})
    assert response.status_code == 201, response.text
    assert response.json()["number"] == 2 and response.json()["status"] == "draft"
    invalid = original["document"]["plan"]
    invalid["steps"][0]["dependencies"] = [0]
    assert client.post(f"/api/v1/gtm/plans/{original['id']}/revisions", headers=a, json=invalid).status_code == 422
    invalid["steps"][0]["dependencies"] = []
    invalid["cost_estimate_cents"] = 100
    assert client.post(f"/api/v1/gtm/plans/{original['id']}/revisions", headers=a, json=invalid).status_code == 422


def test_restart_after_result_commit_reuses_completed_research(client, fake_research, monkeypatch):
    from backend import research_service
    a = signup(client, "committed-result@example.com")
    wid = UUID(a["X-Workspace-ID"])
    cycle = approve(client, a, proposal(client, a))
    captures = []
    original_retrieve = research_service.retrieve
    def capture(url):
        captures.append(url)
        return original_retrieve(url)
    monkeypatch.setattr(research_service, "retrieve", capture)
    first = client.portal.call(worker.claim_next, wid)
    result = client.portal.call(worker.perform, wid, first)
    async def expire():
        async with AsyncSessionLocal() as db:
            worker.bind(db, wid)
            command = await db.scalar(select(ActionCommand))
            command.lease_until = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire)
    second = client.portal.call(worker.claim_next, wid)
    recovered = client.portal.call(worker.perform, wid, second)
    assert recovered == result and len(captures) == 1
    client.portal.call(worker.finish, wid, second, recovered)
    assert client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()["status"] == "completed"


def test_workspace_active_command_limit(client):
    a = signup(client, "admission@example.com")
    wid = UUID(a["X-Workspace-ID"])
    plan = proposal(client, a)
    cycles = [approve(client, a, plan)]
    for _ in range(2):
        next_plan = client.post(f"/api/v1/gtm/goals/{plan['goal_id']}/plans", headers=a, json={"mode": "research_template"}).json()
        cycles.append(approve(client, a, next_plan))
    assert client.portal.call(worker.claim_next, wid)
    assert client.portal.call(worker.claim_next, wid)
    assert client.portal.call(worker.claim_next, wid) is None
    assert client.post(f"/api/v1/gtm/cycles/{cycles[0]['id']}/control", headers=a, json={"action": "cancel"}).status_code == 200
    assert client.portal.call(worker.claim_next, wid)
