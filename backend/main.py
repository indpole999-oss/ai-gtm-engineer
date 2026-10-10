"""
AI GTM Engineer - FastAPI Backend Entry Point
Steps 27-33: Backend setup, JWT auth, CORS, all routes
"""

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn
import logging
import time
import uuid
import re
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from backend.abuse import auth_limiter
from backend.admission import allow_auth
import asyncio

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

from backend.tenancy import require_workspace

from backend.routers import workspaces, record_management, oauth

configure_logging()
logger = logging.getLogger(__name__)
security = HTTPBearer()


async def staging_execution_loop():
    """Restart after transient failures; retain durable leases for reconciliation."""
    from backend.execution_worker import main as execution_worker_main

    while True:
        try:
            await execution_worker_main()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("staging_worker_unavailable", extra={"error_type": type(error).__name__})
        else:
            logger.warning("staging_worker_exited")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting AI GTM Engineer backend...")

    # Schema evolution is performed only by Alembic release commands.
    logger.info("Database initialization complete.")

    # Staging runs the durable execution loop in the same single-instance API
    # process so approved plans can execute without a separate paid worker.
    worker_task = None
    from backend.staging_dependency_probe import probe_enabled, run as run_source_probe
    probe_task = asyncio.create_task(run_source_probe()) if probe_enabled() else None
    if settings.EMBEDDED_EXECUTION_WORKER and settings.APP_ENV.strip().lower() != "test":
        worker_task = asyncio.create_task(staging_execution_loop(), name="execution-worker")
        logger.info("Staging execution worker started.")
    try:
        yield
    finally:
        if probe_task is not None:
            probe_task.cancel()
            try:
                await probe_task
            except asyncio.CancelledError:
                pass
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Staging execution worker stopped.")
        logger.info("Shutting down...")


app = FastAPI(
    title="AI GTM Engineer API",
    description="Autonomous AI GTM Engineer API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, error):
    # Pydantic error input/context may echo credentials or uploaded source content.
    return JSONResponse({"detail": "Invalid request"}, status_code=422)


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
        response = None
        if request.method == "POST" and request.url.path.rstrip("/") in {"/api/v1/auth/login", "/api/v1/auth/register"}:
            peer = request.client.host if request.client else "unknown"
            try:
                allowed = (await asyncio.wait_for(allow_auth(peer), timeout=3)
                           if settings.AUTH_ADMISSION_STORE == "database" else auth_limiter.allow(peer))
                if not allowed:
                    response = JSONResponse({"detail": "Too many authentication attempts"}, status_code=429, headers={"Retry-After": "60"})
            except Exception:
                response = JSONResponse({"detail": "Authentication temporarily unavailable"}, status_code=503, headers={"Retry-After": "60"})
        if response is None:
            try:
                response = await call_next(request)
            except Exception:
                # Arbitrary exception strings can contain provider payloads or credentials.
                logger.error("request_failed")
                response = JSONResponse({"detail": "An internal error occurred", "request_id": request_id}, status_code=500)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": getattr(request.scope.get("route"), "path", "unmatched"),
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "workspace_id": getattr(request.state, "workspace_id", None),
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
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/companies",
    tags=["Companies"],
)

app.include_router(
    contacts.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/contacts",
    tags=["Contacts"],
)

app.include_router(
    leads.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/leads",
    tags=["Leads"],
)

app.include_router(
    emails.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/emails",
    tags=["Emails"],
)

app.include_router(
    crm.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/crm",
    tags=["CRM"],
)

app.include_router(
    calendar.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/calendar",
    tags=["Calendar"],
)

app.include_router(
    agents.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/agents",
    tags=["Agents"],
)

app.include_router(
    workflows.router,
    dependencies=[Depends(require_workspace)],
    prefix="/api/v1/workflows",
    tags=["Workflows"],
)

from backend.routers import brain
from backend.routers import research
from backend.routers import planning
from backend.routers import outreach
from backend.routers import outcomes
from backend.routers import insights
from backend.routers import operations
app.include_router(operations.router, prefix="/api/v1", tags=["Operations"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights and GTM gaps"])
app.include_router(outcomes.router, prefix="/api/v1/outcomes", tags=["Pipeline and outcomes"])
from backend.routers import inbox
app.include_router(inbox.router, prefix="/api/v1/inbox", tags=["Inbox"])
app.include_router(outreach.router, prefix="/api/v1/outreach", tags=["Outreach"])
app.include_router(planning.router, prefix="/api/v1/gtm", tags=["GTM planning"])
app.include_router(research.router, prefix="/api/v1/research", tags=["Research"])
app.include_router(brain.router, prefix="/api/v1/company-brain", tags=["Company Brain"])
app.include_router(oauth.router, prefix="/api/v1/calendar", tags=["OAuth"])
app.include_router(workspaces.router, prefix="/api/v1/workspaces", tags=["Workspaces"])
app.include_router(record_management.router, prefix="/api/v1", dependencies=[Depends(require_workspace)])

# Universal customer integrations
app.include_router(
    integrations.router,
    dependencies=[Depends(require_workspace)],
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
