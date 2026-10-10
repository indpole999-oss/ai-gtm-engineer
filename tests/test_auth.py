"""Basic local authentication behavior without external services."""


def test_register_login_and_current_user(client):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "phase0@example.com",
            "password": "test-password-only",
            "full_name": "Phase Zero",
        },
    )
    assert registration.status_code == 200
    token = registration.json()["access_token"]

    profile = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "phase0@example.com"

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "phase0@example.com", "password": "test-password-only"},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_duplicate_registration_and_bad_login_are_rejected(client):
    payload = {"email": "duplicate@example.com", "password": "test-password-only"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 200
    assert client.post("/api/v1/auth/register", json=payload).status_code == 400

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "duplicate@example.com", "password": "incorrect"},
    )
    assert login.status_code == 401


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/v1/companies/")
    assert response.status_code == 401
