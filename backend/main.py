"""
AI GTM Engineer - FastAPI Backend Entry Point
Steps 27-33: Backend setup, JWT auth, CORS, all routes
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn
import logging
import time
import uuid
import re

from backend.config import settings
from backend.database import engine, Base
from backend.logging_config import configure_logging, request_id_context
from backend.routers import (
    auth,
    companies,
    contacts,
    leads,
    emails,
    crm,
    calendar,
    agents,
    workflows,
    health,
    integrations,
)

configure_logging()
logger = logging.getLogger(__name__)
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting AI GTM Engineer backend...")

    if settings.AUTO_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialization complete.")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="AI GTM Engineer API",
    description="Autonomous AI GTM Engineer API",
    version="1.0.0",
    lifespan=lifespan,
)


# ==============================
# CORS
# ==============================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attach a safe correlation ID and record one structured access log."""
    supplied_request_id = request.headers.get("X-Request-ID", "")[:128]
    request_id = (
        supplied_request_id
        if re.fullmatch(r"[A-Za-z0-9._-]+", supplied_request_id)
        else str(uuid.uuid4())
    )
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        request_id_context.reset(token)


# ==============================
# API ROUTES
# ==============================

app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["Health"],
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Auth"],
)

app.include_router(
    companies.router,
    prefix="/api/v1/companies",
    tags=["Companies"],
)

app.include_router(
    contacts.router,
    prefix="/api/v1/contacts",
    tags=["Contacts"],
)

app.include_router(
    leads.router,
    prefix="/api/v1/leads",
    tags=["Leads"],
)

app.include_router(
    emails.router,
    prefix="/api/v1/emails",
    tags=["Emails"],
)

app.include_router(
    crm.router,
    prefix="/api/v1/crm",
    tags=["CRM"],
)

app.include_router(
    calendar.router,
    prefix="/api/v1/calendar",
    tags=["Calendar"],
)

app.include_router(
    agents.router,
    prefix="/api/v1/agents",
    tags=["Agents"],
)

app.include_router(
    workflows.router,
    prefix="/api/v1/workflows",
    tags=["Workflows"],
)

# Universal customer integrations
app.include_router(
    integrations.router,
    prefix="/api/v1",
    tags=["Integrations"],
)


# ==============================
# ROOT
# ==============================

@app.get("/")
async def root():
    return {
        "message": "AI GTM Engineer API",
        "version": "1.0.0",
        "status": "healthy",
    }


# ==============================
# LOCAL DEVELOPMENT
# ==============================

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
