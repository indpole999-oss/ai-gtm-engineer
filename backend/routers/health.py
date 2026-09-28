"""Health check router"""

from fastapi import APIRouter
from datetime import datetime
import asyncio
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.database import engine

EXPECTED_REVISION = "20260926_0012"

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "AI GTM Engineer API",
        "version": "1.0.0",
    }


async def database_ready():
    async with engine.connect() as connection:
        revisions = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
        return revisions == [EXPECTED_REVISION]


@router.get("/ready")
async def readiness_check():
    """Bounded, read-only schema probe; never expose database errors or credentials."""
    try:
        ready = await asyncio.wait_for(database_ready(), timeout=3)
    except Exception:
        ready = False
    return JSONResponse({"status": "ready" if ready else "not_ready"}, status_code=200 if ready else 503)
