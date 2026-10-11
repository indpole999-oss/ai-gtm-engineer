import asyncio
from unittest.mock import AsyncMock, Mock
import pytest
from backend import execution_worker as worker


@pytest.mark.asyncio
async def test_stop_before_start_prevents_database_poll(monkeypatch):
    stop = asyncio.Event()
    stop.set()
    session = Mock(side_effect=AssertionError("No poll after stop"))
    monkeypatch.setattr(worker, "AsyncSessionLocal", session)
    await worker.main(stop)
    session.assert_not_called()


@pytest.mark.asyncio
async def test_stop_drains_current_work_without_claiming_next_workspace(monkeypatch):
    stop, entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def scalars(self, *args): return Mock(all=lambda: ["synthetic-a", "synthetic-b"])
    monkeypatch.setattr(worker, "AsyncSessionLocal", Session)
    finished = []
    async def run_once(workspace):
        entered.set()
        await release.wait()
        finished.append(workspace)
    run = AsyncMock(side_effect=run_once)
    monkeypatch.setattr(worker, "run_once", run)
    task = asyncio.create_task(worker.main(stop))
    await asyncio.wait_for(entered.wait(), 1)
    stop.set()
    assert not task.done()
    release.set()
    await asyncio.wait_for(task, 1)
    assert finished == ["synthetic-a"]
    run.assert_awaited_once_with("synthetic-a")


@pytest.mark.asyncio
async def test_emergency_cancellation_propagates_without_false_completion(monkeypatch):
    entered = asyncio.Event()
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def scalars(self, *args): return Mock(all=lambda: ["synthetic-a"])
    monkeypatch.setattr(worker, "AsyncSessionLocal", Session)
    async def run_once(workspace):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(worker, "run_once", run_once)
    task = asyncio.create_task(worker.main(asyncio.Event()))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
