from backend.abuse import AuthLimiter


def test_limiter_expiry_and_bounded_capacity(monkeypatch):
    monkeypatch.setattr("backend.abuse.time.monotonic", lambda: 0)
    limiter = AuthLimiter(limit=2, capacity=1)
    assert limiter.allow("peer") and limiter.allow("peer")
    assert not limiter.allow("peer") and not limiter.allow("other")
    monkeypatch.setattr("backend.abuse.time.monotonic", lambda: 61)
    assert limiter.allow("other")


def test_auth_admission_cannot_be_bypassed_by_forwarded_header(client, monkeypatch):
    monkeypatch.setattr("backend.main.auth_limiter", AuthLimiter(limit=2))
    for index in range(2):
        assert client.post("/api/v1/auth/login", data={"username": "absent@example.com", "password": "invalid"}, headers={"X-Forwarded-For": str(index)}).status_code == 401
    response = client.post("/api/v1/auth/register", json={}, headers={"X-Forwarded-For": "different"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.headers["x-request-id"]
    assert client.get("/api/v1/health").status_code == 200


def test_unexpected_error_is_safe_and_correlated(client, monkeypatch):
    def broken(value):
        raise RuntimeError("private provider payload and credentials")
    monkeypatch.setattr("backend.routers.auth.hash_password", broken)
    response = client.post("/api/v1/auth/register", json={"email": "failure@example.com", "password": "safe-test-password"}, headers={"X-Request-ID": "safe-correlation"})
    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred", "request_id": "safe-correlation"}
    assert response.headers["x-request-id"] == "safe-correlation"


def test_invalid_passwords_never_echo_secret_or_raise_server_error(client):
    for password in ("short", "x" * 73, "🔒" * 20):
        response = client.post("/api/v1/auth/register", json={"email": "invalid@example.com", "password": password})
        assert response.status_code == 422
        assert response.json() == {"detail": "Invalid request"}
