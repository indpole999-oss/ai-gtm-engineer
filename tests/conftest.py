"""Test-safe environment and database fixtures."""

import os
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DIRECTORY = TemporaryDirectory(prefix="gaps-tests-")
TEST_DB = Path(TEST_DIRECTORY.name) / "test.db"
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DB.as_posix()}",
        "SECRET_KEY": "test-only-secret-key-that-is-long-enough",
        "ALLOW_LEGACY_ENV_CREDENTIALS": "false",
        "INTEGRATION_ENCRYPTION_KEY": "",
    }
)

from backend.main import app  # noqa: E402
from backend.database import engine, Base  # noqa: E402


@pytest.fixture()
def client():
    TEST_DB.unlink(missing_ok=True)
    async def initialize_test_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    with TestClient(app) as test_client:
        test_client.portal.call(initialize_test_schema)
        try:
            yield test_client
        finally:
            # Close pooled connections before deleting the SQLite database.
            test_client.portal.call(engine.dispose)
    TEST_DB.unlink(missing_ok=True)
