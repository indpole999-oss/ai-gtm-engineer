"""Invoked only against the disposable migrated PostgreSQL CI database."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.ext.asyncio import create_async_engine
from backend import admission
from backend.database import engine


async def main():
    async def fixed(connection):
        return 100
    admission.database_window = fixed
    other = create_async_engine(engine.url)
    try:
        results = await asyncio.gather(*(admission.allow_auth("ci-peer", database=engine if i % 2 else other, peer_limit=3) for i in range(12)))
        assert sum(results) == 3, results
        assert not await admission.allow_auth("other-peer", global_limit=12)
    finally:
        await other.dispose()
        await engine.dispose()


asyncio.run(main())
