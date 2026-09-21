"""Real API and persistence tests: no mocked authorization or query filters."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, update
from fastapi import HTTPException
from backend.database import (AsyncSessionLocal, Company, Contact, CRMRecord, EmailLog,
                              Meeting, Integration, WorkspaceMembership)


def signup(client, email):
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "test-password-only"})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    workspaces = client.get("/api/v1/workspaces", headers=headers).json()
    assert len(workspaces) == 1 and workspaces[0]["role"] == "owner"
    headers["X-Workspace-ID"] = workspaces[0]["id"]
    return headers


@pytest.fixture
def tenants(client):
    a = signup(client, "a@example.com")
    b = signup(client, "b@example.com")
    return a, b


def company(client, headers, name="Company", domain="same.example"):
    response = client.post("/api/v1/companies/", headers=headers, json={"name": name, "domain": domain})
    assert response.status_code == 200, response.text
    return response.json()


def contact(client, headers, company_id):
    response = client.post("/api/v1/contacts/", headers=headers, json={
        "company_id": company_id, "first_name": "Test", "last_name": "Buyer", "email": "buyer@example.com"})
    assert response.status_code == 200, response.text
    return response.json()


def test_company_contact_collections_ids_mutations_and_relationships(client, tenants):
    a, b = tenants
    ac, bc = company(client, a), company(client, b)
    at, bt = contact(client, a, ac["id"]), contact(client, b, bc["id"])
    for path, aid, bid in (("companies", ac["id"], bc["id"]), ("contacts", at["id"], bt["id"]), ("leads", at["id"], bt["id"])):
        rows = client.get(f"/api/v1/{path}/", headers=a).json()
        assert [row["id"] for row in rows] == [aid]
        if path == "leads":
            continue
        assert client.get(f"/api/v1/{path}/{bid}", headers=a).status_code == 404
        assert client.delete(f"/api/v1/{path}/{bid}", headers=a).status_code == 404
        payload = {"name": "stolen"} if path == "companies" else {"first_name": "stolen"}
        assert client.patch(f"/api/v1/{path}/{bid}", headers=a, json=payload).status_code == 404
        assert client.get(f"/api/v1/{path}/{bid}", headers=b).status_code == 200
    assert client.patch(f"/api/v1/contacts/{at['id']}", headers=a, json={"company_id": bc["id"]}).status_code == 404
    assert client.post("/api/v1/contacts/", headers=a, json={"company_id": bc["id"], "first_name": "Bad", "last_name": "Link", "email": "bad@example.com"}).status_code == 404
    spoofed = dict(a, **{"X-Workspace-ID": b["X-Workspace-ID"]})
    assert client.get("/api/v1/companies/", headers=spoofed).status_code == 403
    assert client.get("/api/v1/companies/", headers=dict(a, **{"X-Workspace-ID": "invalid"})).status_code == 400


def test_all_other_customer_records_are_isolated(client, tenants):
    a, b = tenants
    bc = company(client, b)
    bt = contact(client, b, bc["id"])
    uid = client.get("/api/v1/auth/me", headers=b).json()["id"]

    async def seed():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(b["X-Workspace-ID"]), workspace_role="owner")
            rows = {"crm": CRMRecord(contact_id=UUID(bt["id"])),
                    "emails": EmailLog(contact_id=UUID(bt["id"]), subject="Secret"),
                    "calendar": Meeting(contact_id=UUID(bt["id"]), title="Secret", contact_email="buyer@example.com"),
                    "integrations": Integration(user_id=UUID(uid), category="crm", provider="hubspot",
                                                credentials="encrypted-secret", config={"access_token": "hidden"})}
            db.add_all(rows.values())
            await db.commit()
            return {path: str(row.id) for path, row in rows.items()}

    ids = client.portal.call(seed)
    for path, record_id in ids.items():
        suffix = "" if path == "integrations" else "/"
        rows = client.get(f"/api/v1/{path}{suffix}", headers=a).json()
        assert (rows["integrations"] if path == "integrations" else rows) == []
        assert client.get(f"/api/v1/{path}/{record_id}", headers=a).status_code == 404
        assert client.delete(f"/api/v1/{path}/{record_id}", headers=a).status_code == 404
        assert client.get(f"/api/v1/{path}/{record_id}", headers=b).status_code == 200
    integration_id = ids["integrations"]
    assert client.put(f"/api/v1/integrations/{integration_id}", headers=a, json={"status": "connected"}).status_code == 404
    assert client.post(f"/api/v1/integrations/{integration_id}/test", headers=a).status_code == 404
    assert "encrypted-secret" not in client.get(f"/api/v1/integrations/{integration_id}", headers=b).text
    assert "hidden" not in client.get(f"/api/v1/integrations/{integration_id}", headers=b).text


@pytest.mark.parametrize("role,write,delete,integrations", [("viewer",403,403,403),("member",200,403,403),("admin",200,200,404),("owner",200,200,404)])
def test_role_policy(client, tenants, role, write, delete, integrations):
    a, b = tenants
    row = company(client, a)
    uid = client.get("/api/v1/auth/me", headers=b).json()["id"]
    response = client.put("/api/v1/workspaces/current/memberships", headers=a,
                          json={"user_id": uid, "role": role})
    assert response.status_code == 200
    actor = dict(b, **{"X-Workspace-ID": a["X-Workspace-ID"]})
    assert client.get(f"/api/v1/companies/{row['id']}", headers=actor).status_code == 200
    assert client.patch(f"/api/v1/companies/{row['id']}", headers=actor, json={"name":"updated"}).status_code == write
    assert client.delete(f"/api/v1/companies/{row['id']}", headers=actor).status_code == delete
    assert client.put(f"/api/v1/integrations/{uuid4()}", headers=actor, json={"status":"connected"}).status_code == integrations
    if role != "owner":
        assert client.put("/api/v1/workspaces/current/memberships", headers=actor, json={"user_id":uid,"role":"owner"}).status_code == 403


def test_suspended_membership_and_last_owner(client, tenants):
    a, b = tenants
    uid = client.get("/api/v1/auth/me", headers=a).json()["id"]
    assert client.put("/api/v1/workspaces/current/memberships", headers=a, json={"user_id":uid,"role":"viewer"}).status_code == 409
    buid = client.get("/api/v1/auth/me", headers=b).json()["id"]
    assert client.put("/api/v1/workspaces/current/memberships", headers=a, json={"user_id":buid,"role":"member","status":"suspended"}).status_code == 200
    assert client.get("/api/v1/companies/", headers=dict(b, **{"X-Workspace-ID":a["X-Workspace-ID"]})).status_code == 403


def test_sessions_fail_closed_and_reject_forged_ownership(client, tenants):
    a, b = tenants
    company(client,b)
    async def check():
        async with AsyncSessionLocal() as db:
            assert list((await db.scalars(select(Company))).all()) == []
            db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="owner")
            db.add(Company(name="forged", workspace_id=UUID(b["X-Workspace-ID"])))
            with pytest.raises(HTTPException):
                await db.flush()
            await db.rollback()
            with pytest.raises(HTTPException):
                await db.execute(update(Company).values(name="bulk attack"))
    client.portal.call(check)


def test_quarantined_legacy_records_remain_invisible(client, tenants):
    from backend.database import engine
    legacy_id = uuid4()
    async def seed_legacy():
        # Simulates an existing unassigned row using the migration connection.
        async with engine.begin() as connection:
            await connection.execute(Company.__table__.insert().values(
                id=legacy_id, name="Unassigned legacy customer", workspace_id=None))
    client.portal.call(seed_legacy)
    for headers in tenants:
        assert client.get("/api/v1/companies/", headers=headers).json() == []
        assert client.get(f"/api/v1/companies/{legacy_id}", headers=headers).status_code == 404
        assert client.patch(f"/api/v1/companies/{legacy_id}", headers=headers, json={"name":"claim"}).status_code == 404
        assert client.delete(f"/api/v1/companies/{legacy_id}", headers=headers).status_code == 404


@pytest.mark.parametrize("path,payload", [
    ("/agents/run", {"agent":"crm","task":"write","context":{"user_id":"spoofed"}}),
    ("/workflows/run", {"workflow_name":"lead_pipeline","context":{}}),
    ("/emails/send", {"contact_id":str(uuid4()),"subject":"x","body":"x"}),
    ("/calendar/book", {"contact_id":str(uuid4())}),
    ("/crm/deal", {"deal_name":"x"}),
])
def test_legacy_side_effects_cannot_bypass_approval(client, tenants, path, payload):
    assert client.post("/api/v1"+path, headers=tenants[0], json=payload).status_code == 409
