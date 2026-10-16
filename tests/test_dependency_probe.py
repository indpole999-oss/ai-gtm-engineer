import asyncio
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from backend import staging_dependency_probe as probe, execution_worker, retrieval


def test_probe_is_staging_only_and_requires_hosted_pause(monkeypatch):
    monkeypatch.setenv("GTM_SOURCE_PROBE_PLAN", "configured")
    monkeypatch.setenv("RENDER_SERVICE_ID", "production")
    assert not probe.probe_enabled()
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-daui93navr4c739a4chg")
    monkeypatch.setenv("GTM_HOSTED_AI_ENABLED", "true")
    assert not probe.probe_enabled()
    monkeypatch.setenv("GTM_HOSTED_AI_ENABLED", "false")
    assert probe.probe_enabled()


def test_probe_reports_real_retriever_rejection_and_resets_trace(monkeypatch):
    def reject(url):
        retrieval.trace_event(stage="http", status=403)
        raise retrieval.RetrievalError("Robots policy unavailable; source not retrieved")
    monkeypatch.setattr(probe, "retrieve", reject)
    result = probe.capture("https://example.com/")
    assert result["status"] == "BLOCKED"
    assert result["http_trace"] == [{"stage": "http", "status": 403}]
    assert "Robots policy unavailable" in result["reason"]
    assert "sha256" not in result
    assert retrieval.retrieval_trace.get() is None


@pytest.mark.asyncio
async def test_probe_rejects_changed_plan_without_retrieving(monkeypatch):
    monkeypatch.setattr(probe, "probe_enabled", lambda: True)
    for key in ("GTM_SOURCE_PROBE_WORKSPACE", "GTM_SOURCE_PROBE_PLAN"):
        monkeypatch.setenv(key, "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("GTM_SOURCE_PROBE_HASH", "expected")
    db = SimpleNamespace(info={}, scalar=AsyncMock(return_value=SimpleNamespace(content_hash="changed")))
    @asynccontextmanager
    async def session():
        yield db
    monkeypatch.setattr(probe, "AsyncSessionLocal", session)
    monkeypatch.setattr(probe, "capture", lambda url: pytest.fail("Must not retrieve changed plan"))
    await probe.run()
    assert db.info["workspace_role"] == "viewer"


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_worker_heartbeat_requires_completed_database_sweep(monkeypatch, caplog, fails):
    caplog.set_level(logging.INFO)
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: ["workspace"])))
    @asynccontextmanager
    async def session():
        yield db
    monkeypatch.setattr(execution_worker, "AsyncSessionLocal", session)
    monkeypatch.setattr(execution_worker, "run_once", AsyncMock(side_effect=RuntimeError() if fails else None))
    async def stop(_):
        raise asyncio.CancelledError()
    monkeypatch.setattr(execution_worker.asyncio, "sleep", stop)
    with pytest.raises(RuntimeError if fails else asyncio.CancelledError):
        await execution_worker.main()
    assert ("worker_heartbeat" in caplog.text) == (not fails)
    assert "worker_stopped" in caplog.text
