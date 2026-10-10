from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select
from backend.database import AsyncSessionLocal, WorkspaceMembership
from backend.planning_models import ActionCommand
from backend import execution_worker as worker
from test_workspace_security import signup, company, contact
from test_planning_execution import proposal, approve


def test_unapproved_retention_and_referenced_deletion_fail_closed(client):
    a, b = signup(client, "retention-a@example.com"), signup(client, "retention-b@example.com")
    account = company(client, a, domain="deletion.example")
    person = contact(client, a, account["id"])
    assert client.delete("/api/v1/companies/" + account["id"], headers=a).status_code == 409
    assert client.get("/api/v1/contacts/" + person["id"], headers=a).status_code == 200
    approve(client, a, proposal(client, a))
    report = client.get("/api/v1/retention", headers=a).json()
    assert report["automatic_purge_enabled"] is False
    assert report["policy_status"] == "approval_required"
    assert all(d["retention_days"] is None for d in report["datasets"].values())
    assert report["datasets"]["execution_audit"]["records"] > 0
    assert client.get("/api/v1/retention", headers=b).json()["datasets"]["execution_audit"]["records"] == 0
    assert client.get("/api/v1/retention", headers={**a, "X-Workspace-ID": b["X-Workspace-ID"]}).status_code == 403
    async def viewer():
        async with AsyncSessionLocal() as db:
            m = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            m.role = "viewer"
            await db.commit()
    client.portal.call(viewer)
    assert client.get("/api/v1/retention", headers=a).status_code == 403


def test_operational_alerts_are_tenant_scoped(client):
    a, b = signup(client, "alerts-a@example.com"), signup(client, "alerts-b@example.com")
    approve(client, a, proposal(client, a))
    async def stale():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            command = await db.scalar(select(ActionCommand))
            command.status = "running"
            command.lease_until = datetime.utcnow() - timedelta(minutes=1)
            await db.commit()
    client.portal.call(stale)
    report = client.get("/api/v1/operations", headers=a).json()
    assert report["alerts"] == ["expired_leases"]
    assert report["worker_liveness"] == "not_measured"
    assert client.get("/api/v1/operations", headers=b).json()["alerts"] == []
