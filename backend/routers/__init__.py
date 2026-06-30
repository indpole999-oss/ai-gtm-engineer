"""Routers package - all FastAPI route modules"""

from backend.routers import auth, companies, contacts, leads, emails, crm, calendar, agents, workflows, health

__all__ = ["auth", "companies", "contacts", "leads", "emails", "crm", "calendar", "agents", "workflows", "health"]
