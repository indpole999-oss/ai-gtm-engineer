"""Application startup and health contract tests."""


def test_application_starts_and_serves_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.headers["x-request-id"]


def test_health_endpoint_returns_service_metadata(client):
    request_id = "phase0-health-check"
    response = client.get("/api/v1/health", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "AI GTM Engineer API"
