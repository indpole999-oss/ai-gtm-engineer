"""Local Qwen3 adapters must not spend their deadline on hidden thinking output.

These tests intercept network operations before any provider traffic.
"""
import asyncio
import pytest

from backend import planning_service, research_service


class Intercepted(RuntimeError):
    pass


class CaptureClient:
    def __init__(self, captured):
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json):
        self.captured.update(json)
        raise Intercepted("request intercepted before network")


def test_local_research_disables_model_thinking(monkeypatch):
    payload = {}
    monkeypatch.setattr(
        research_service.httpx,
        "AsyncClient",
        lambda **kwargs: CaptureClient(payload),
    )
    spans = [{"url": "https://example.org/fixture", "spans": [{
        "id": "fd61e12e-e30c-48f7-adcb-fc69d23614cc",
        "text": "Synthetic testing fixture, not a real company.",
    }]}]
    with pytest.raises(Intercepted):
        asyncio.run(research_service.LocalResearchProvider().analyze(
            {"icp": "Synthetic QA"}, spans, {"name": "Fictional QA"}
        ))
    assert payload["model"] == "qwen3:4b"
    assert payload["think"] is False
    assert payload["stream"] is False
    assert isinstance(payload["format"], dict)


def test_local_planner_disables_model_thinking(monkeypatch):
    payload = {}
    monkeypatch.setattr(
        planning_service.httpx,
        "AsyncClient",
        lambda **kwargs: CaptureClient(payload),
    )
    with pytest.raises(Intercepted):
        asyncio.run(planning_service.LocalPlanner().plan(
            {"objective": "Synthetic QA research plan"}
        ))
    assert payload["model"] == "qwen3:4b"
    assert payload["think"] is False
    assert payload["stream"] is False
    assert isinstance(payload["format"], dict)
