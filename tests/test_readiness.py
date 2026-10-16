"""Readiness must fail closed without leaking infrastructure details."""
import pytest
from sqlalchemy import text
from backend.database import engine
from backend.routers import health


def test_readiness_revision_matches_migration_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == [health.EXPECTED_REVISION]


def test_readiness_requires_exact_migration(client):
    assert client.get("/api/v1/ready").status_code == 503

    async def revision(value):
        async with engine.begin() as db:
            await db.execute(text("CREATE TABLE IF NOT EXISTS alembic_version(version_num VARCHAR(32))"))
            await db.execute(text("DELETE FROM alembic_version"))
            await db.execute(text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": value})

    client.portal.call(revision, "older_schema")
    assert client.get("/api/v1/ready").status_code == 503
    client.portal.call(revision, health.EXPECTED_REVISION)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.parametrize("error", [RuntimeError("postgresql://user:secret@private/db"), TimeoutError()])
def test_readiness_failure_is_safe_and_liveness_remains_available(client, monkeypatch, error):
    async def unavailable():
        raise error
    monkeypatch.setattr(health, "database_ready", unavailable)
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert response.headers["x-request-id"]
    assert client.get("/api/v1/health").status_code == 200
