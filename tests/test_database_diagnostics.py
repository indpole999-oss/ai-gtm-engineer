import json
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend import database
from backend.logging_config import JsonFormatter


@pytest.mark.asyncio
@pytest.mark.parametrize("error,expected_log", [
    (HTTPException(401, "synthetic-sensitive-detail"), False),
    (HTTPException(503, "synthetic-sensitive-detail"), False),
    (RuntimeError("synthetic-sensitive-detail"), True),
])
async def test_session_rollback_and_safe_failure_diagnostics(monkeypatch, caplog, error, expected_log):
    class Session:
        commit = AsyncMock()
        rollback = AsyncMock()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    session = Session()
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: session)
    dependency = database.get_db()
    assert await anext(dependency) is session
    with pytest.raises(type(error)):
        await dependency.athrow(error)
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    records = [r for r in caplog.records if r.name == "backend.database"]
    assert bool(records) == expected_log
    if records:
        formatted = JsonFormatter().format(records[-1])
        assert json.loads(formatted)["error_type"] == "RuntimeError"
        assert "synthetic-sensitive-detail" not in formatted
