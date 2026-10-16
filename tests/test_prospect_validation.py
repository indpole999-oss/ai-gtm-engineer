"""Invalid customer input must not create blank records or pipeline entries."""
import pytest
from test_workspace_security import signup


def test_duplicate_prospects_are_honest_conflicts_and_tenant_scoped(client):
    a = signup(client, "duplicate-a@example.com")
    b = signup(client, "duplicate-b@example.com")
    for headers in (a, b):
        payload = {"name": "Acme", "domain": "example.com"}
        account = client.post("/api/v1/companies/", headers=headers, json=payload).json()
        assert client.post("/api/v1/companies/", headers=headers, json=payload).status_code == 409
        buyer = {"company_id": account["id"], "first_name": "Jane", "last_name": "Buyer", "email": "jane@example.com"}
        assert client.post("/api/v1/contacts/", headers=headers, json=buyer).status_code == 200
        assert client.post("/api/v1/contacts/", headers=headers, json=buyer).status_code == 409
        assert len(client.get("/api/v1/companies/", headers=headers).json()) == 1
        assert len(client.get("/api/v1/contacts/", headers=headers).json()) == 1
        assert len(client.get("/api/v1/outcomes/pipeline", headers=headers).json()) == 2


@pytest.mark.parametrize("name", ["", "   ", "\t\n", "a" * 256])
def test_invalid_account_name_never_persists(client, name):
    headers = signup(client, "validation-account@example.com")
    assert client.post("/api/v1/companies/", headers=headers, json={"name": name}).status_code == 422
    assert client.get("/api/v1/companies/", headers=headers).json() == []
    assert client.get("/api/v1/outcomes/pipeline", headers=headers).json() == []


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize("value", ["", "   ", "a" * 101])
def test_invalid_contact_name_and_edit_preserve_records(client, field, value):
    headers = signup(client, "validation-contact@example.com")
    account = client.post("/api/v1/companies/", headers=headers, json={"name": "  Acme  "}).json()
    assert account["name"] == "Acme"
    valid = {"company_id": account["id"], "first_name": " Jane ", "last_name": " Buyer ", "email": "jane@example.com"}
    assert client.post("/api/v1/contacts/", headers=headers, json={**valid, field: value}).status_code == 422
    assert client.get("/api/v1/contacts/", headers=headers).json() == []
    saved = client.post("/api/v1/contacts/", headers=headers, json=valid).json()
    assert saved["first_name"] == "Jane" and saved["last_name"] == "Buyer"
    before = client.get("/api/v1/outcomes/pipeline", headers=headers).json()
    assert client.patch(f"/api/v1/contacts/{saved['id']}", headers=headers, json={field: value}).status_code == 422
    assert client.patch(f"/api/v1/companies/{account['id']}", headers=headers, json={"name": "   "}).status_code == 422
    assert client.get(f"/api/v1/contacts/{saved['id']}", headers=headers).json()[field] == saved[field]
    assert client.get("/api/v1/outcomes/pipeline", headers=headers).json() == before
