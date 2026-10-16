import httpx
import pytest
from backend import research_readiness
from test_workspace_security import signup


def test_paused_readiness_is_authenticated_and_never_calls_provider(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-key")
    monkeypatch.setenv("GTM_HOSTED_AI_ENABLED", "false")
    monkeypatch.setattr(research_readiness.httpx, "AsyncClient", lambda **kw: pytest.fail("Paused readiness must not call a provider"))
    assert client.get("/api/v1/research/readiness").status_code in (401, 403)
    a = signup(client, "readiness@example.com")
    result = client.get("/api/v1/research/readiness", headers=a).json()
    assert result["state"] == "paused" and result["can_attempt"] is False
    assert "synthetic-key" not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("models,state", [([{"name": "qwen3:4b"}], "model_available"), ([], "model_missing"), ([{}], "unavailable")])
async def test_local_readiness_checks_installed_model_only(monkeypatch, models, state):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ-API-KEY", raising=False)
    monkeypatch.setenv("GTM_LOCAL_MODEL", "qwen3:4b")
    original = httpx.AsyncClient
    def handle(request):
        assert request.method == "GET" and request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": models})
    monkeypatch.setattr(research_readiness.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    result = await research_readiness.model_readiness()
    assert result["state"] == state and result["can_attempt"] == (state == "model_available")
