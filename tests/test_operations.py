from uuid import UUID
from sqlalchemy import select
from backend.database import AsyncSessionLocal, WorkspaceMembership
from test_workspace_security import signup
from test_planning_execution import proposal, approve


def test_operations_scope_and_approval_inventory(client):
    a, b = signup(client, "ops-a@example.com"), signup(client, "ops-b@example.com")
    plan = proposal(client, a)
    result = client.get("/api/v1/operations", headers=a)
    assert result.status_code == 200
    assert result.json()["plans"] == {"draft": 1}
    assert result.json()["commands"] == {}
    approve(client, a, plan)
    result = client.get("/api/v1/operations", headers=a).json()
    assert result["commands"] == {"queued": 1}
    assert result["cycles"] == {"running": 1}
    assert result["provider_cost"]["amount"] is None
    assert client.get("/api/v1/operations", headers=b).json()["commands"] == {}
    assert client.get("/api/v1/operations", headers={**a, "X-Workspace-ID": b["X-Workspace-ID"]}).status_code == 403
    assert client.get("/api/v1/operations").status_code == 401
    async def viewer():
        async with AsyncSessionLocal() as db:
            member = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            member.role = "viewer"
            await db.commit()
    client.portal.call(viewer)
    assert client.get("/api/v1/operations", headers=a).status_code == 403
