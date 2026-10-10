import asyncio
from unittest.mock import AsyncMock

import pytest
from backend import main


@pytest.mark.asyncio
@pytest.mark.parametrize("environment,enabled,starts", [
    ("test", True, False), ("production", False, False),
    ("staging", False, False), ("staging", True, True), ("production", True, True),
])
async def test_embedded_worker_requires_explicit_opt_in(monkeypatch, environment, enabled, starts):
    monkeypatch.setattr(main.settings, "APP_ENV", environment)
    monkeypatch.setattr(main.settings, "EMBEDDED_EXECUTION_WORKER", enabled)
    entered, cancelled = asyncio.Event(), asyncio.Event()
    async def worker():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    monkeypatch.setattr(main, "staging_execution_loop", worker)
    async with main.lifespan(main.app):
        if starts:
            await asyncio.wait_for(entered.wait(), 1)
        else:
            await asyncio.sleep(0)
            assert not entered.is_set()
    assert cancelled.is_set() == starts


@pytest.mark.asyncio
async def test_staging_worker_restarts_without_logging_raw_errors(monkeypatch, caplog):
    from backend import execution_worker
    restarted = asyncio.Event()
    attempts = 0
    async def worker():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("secret-provider-payload")
        restarted.set()
        await asyncio.Event().wait()
    delay = AsyncMock()
    monkeypatch.setattr(execution_worker, "main", worker)
    monkeypatch.setattr(main.asyncio, "sleep", delay)
    task = asyncio.create_task(main.staging_execution_loop())
    await asyncio.wait_for(restarted.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    delay.assert_awaited_once_with(5)
    assert "staging_worker_unavailable" in caplog.text
    assert "secret-provider-payload" not in caplog.text
