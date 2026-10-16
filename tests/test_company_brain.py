"""Published knowledge is reviewed, tenant-scoped and permanently versioned."""
from uuid import UUID
import pytest
from sqlalchemy import select
from backend.database import AsyncSessionLocal, WorkspaceMembership
from test_workspace_security import signup

BASE = "/api/v1/company-brain"
PROFILE = {key: "Customer-reviewed " + key for key in ("company", "product_service", "value_proposition", "icp", "buyer_personas", "gtm_objectives")}


def draft(client, headers):
    response = client.post(BASE + "/drafts", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def save(client, headers, row, **changes):
    body = {"revision": row["revision"], "profile": PROFILE,
            "sources": [{"key": "case-1", "kind": "case_study", "title": "Customer case", "url": "https://example.com/case", "content": "Reviewed evidence"}],
            "claims": [{"text": "Reviewed promise", "disposition": "approved", "source_key": "case-1"},
                       {"text": "Guaranteed revenue", "disposition": "prohibited", "source_key": None}]}
    body.update(changes)
    return client.put(f"{BASE}/versions/{row['id']}", headers=headers, json=body)


def test_brain_review_publish_clone_and_stale_edit(client):
    a = signup(client, "brain@example.com")
    row = draft(client, a)
    assert draft(client, a)["id"] == row["id"]
    path = f"{BASE}/versions/{row['id']}"
    assert client.post(path + "/publish", headers=a, json={"revision": 1, "reviewed": True}).status_code == 422
    response = save(client, a, row)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["revision"] > row["revision"]
    assert save(client, a, row).status_code == 409
    assert client.post(path + "/publish", headers=a, json={"revision": saved["revision"], "reviewed": False}).status_code == 422
    published = client.post(path + "/publish", headers=a, json={"revision": saved["revision"], "reviewed": True})
    assert published.status_code == 200, published.text
    published = published.json()
    assert len(published["content_hash"]) == 64
    assert save(client, a, published).status_code == 409
    second = draft(client, a)
    assert second["number"] == 2 and second["id"] != row["id"]
    assert second["sources"] == saved["sources"] and second["claims"] == saved["claims"]
    assert save(client, a, second, profile={**PROFILE, "company": "Updated company"}).status_code == 200
    assert client.get(path, headers=a).json() == published


def test_brain_cross_tenant_and_source_reference_validation(client):
    a, b = signup(client, "brain-a@example.com"), signup(client, "brain-b@example.com")
    row = draft(client, b)
    assert client.get(BASE, headers=a).json() == {"versions": []}
    assert client.get(f"{BASE}/versions/{row['id']}", headers=a).status_code == 404
    assert save(client, a, row).status_code == 404
    assert client.post(f"{BASE}/versions/{row['id']}/publish", headers=a, json={"revision": 1, "reviewed": True}).status_code == 404
    assert save(client, b, row, claims=[{"text": "Forged", "disposition": "approved", "source_key": "other-version"}]).status_code == 422
    assert save(client, b, row, workspace_id=a["X-Workspace-ID"]).status_code == 422


@pytest.mark.parametrize("role,write,publish", [("viewer",403,403),("member",200,403),("admin",200,200),("owner",200,200)])
def test_brain_roles(client, role, write, publish):
    a = signup(client, f"brain-{role}@example.com")
    row = draft(client, a)
    row = save(client, a, row).json()
    async def change_role():
        async with AsyncSessionLocal() as db:
            membership = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            membership.role = role
            await db.commit()
    client.portal.call(change_role)
    response = save(client, a, row)
    assert response.status_code == write, response.text
    if write == 200:
        row = response.json()
    assert client.get(f"{BASE}/versions/{row['id']}", headers=a).status_code == 200
    response = client.post(f"{BASE}/versions/{row['id']}/publish", headers=a, json={"revision": row["revision"], "reviewed": True})
    assert response.status_code == publish, response.text


def test_brain_document_preview_is_bounded_and_never_executes(client):
    a = signup(client, "documents@example.com")
    result = client.post(BASE + "/documents/preview", headers=a, files={"file": ("positioning.md", b"# Customer positioning", "text/markdown")})
    assert result.status_code == 200 and result.json()["content"] == "# Customer positioning"
    assert client.post(BASE + "/documents/preview", headers=a, files={"file": ("script.exe", b"data")}).status_code == 422
    assert client.post(BASE + "/documents/preview", headers=a, files={"file": ("large.txt", b"x" * 2000001)}).status_code == 413
    assert client.post(BASE + "/documents/preview", headers=a, files={"file": ("bad.pdf", b"not a PDF")}).status_code == 422
