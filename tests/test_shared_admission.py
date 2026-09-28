import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from backend import admission
from backend.database import engine
from backend.config import settings


def test_independent_pools_share_atomic_limits_and_hash_peers(client, monkeypatch):
    async def fixed(_):
        return 100
    monkeypatch.setattr(admission, "database_window", fixed)
    async def exercise():
        other = create_async_engine(engine.url)
        try:
            results = await asyncio.gather(*(admission.allow_auth("192.0.2.1", database=engine if i % 2 else other, peer_limit=3) for i in range(12)))
            assert sum(results) == 3
            async with engine.connect() as db:
                keys = (await db.execute(select(admission.AuthAdmissionBucket.key))).scalars().all()
                assert all(k == "global" or len(k) == 64 for k in keys)
                assert "192.0.2.1" not in keys
            assert not await admission.allow_auth("new-peer", global_limit=12)
        finally:
            await other.dispose()
    client.portal.call(exercise)
    async def next_window(_):
        return 103
    monkeypatch.setattr(admission, "database_window", next_window)
    assert client.portal.call(admission.allow_auth, "192.0.2.1")


def test_database_limiter_failure_is_closed_and_safe(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ADMISSION_STORE", "database")
    async def broken(peer):
        raise RuntimeError("secret database details")
    monkeypatch.setattr("backend.main.allow_auth", broken)
    r = client.post("/api/v1/auth/login", data={"username": "a", "password": "b"})
    assert r.status_code == 503
    assert r.json() == {"detail": "Authentication temporarily unavailable"}
    assert r.headers["x-request-id"]


def test_database_admission_http_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ADMISSION_STORE", "database")
    monkeypatch.setattr(settings, "AUTH_PEER_LIMIT", 1)
    body = {"username": "missing@example.com", "password": "invalid"}
    assert client.post("/api/v1/auth/login", data=body).status_code == 401
    assert client.post("/api/v1/auth/login", data=body, headers={"X-Forwarded-For": "spoofed"}).status_code == 429
