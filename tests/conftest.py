"""Test-safe environment and database fixtures."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB = Path("/tmp/ai_gtm_engineer_phase0_test.db")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DB}",
        "SECRET_KEY": "test-only-secret-key-that-is-long-enough",
        "ALLOW_LEGACY_ENV_CREDENTIALS": "false",
        "INTEGRATION_ENCRYPTION_KEY": "",
    }
)

from backend.main import app  # noqa: E402
from backend.database import engine  # noqa: E402


@pytest.fixture()
def client():
    TEST_DB.unlink(missing_ok=True)
    with TestClient(app) as test_client:
        try:
            yield test_client
        finally:
            # Close pooled connections before deleting the SQLite database.
            test_client.portal.call(engine.dispose)
    TEST_DB.unlink(missing_ok=True)
