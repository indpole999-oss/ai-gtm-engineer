"""
AI GTM Engineer - FastAPI Backend Entry Point
Steps 27-33: Backend setup, JWT auth, CORS, all routes
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn
import logging

from backend.config import settings
from backend.database import engine, Base
from backend.routers import (
    auth, companies, contacts, leads,
    emails, crm, calendar, agents,
    workflows, health
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
      """Startup and shutdown events"""
      logger.info("Starting AI GTM Engineer backend...")
      async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ready.")
    yield
    logger.info("Shutting down...")


app = FastAPI(
      title="AI GTM Engineer API",
      description="Autonomous AI GTM Engineer API",
      version="1.0.0",
      lifespan=lifespan,
  )

app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.CORS_ORIGINS,
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["Contacts"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(emails.router, prefix="/api/v1/emails", tags=["Emails"])
app.include_router(crm.router, prefix="/api/v1/crm", tags=["CRM"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["Calendar"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])


@app.get("/")
async def root():
      return {"message": "AI GTM Engineer API", "version": "1.0.0", "status": "healthy"}


if __name__ == "__main__":
      uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
