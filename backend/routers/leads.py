"""Leads router - manage leads pipeline"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db, Contact
from backend.routers.auth import get_current_user

router = APIRouter()


class LeadUpdate(BaseModel):
      status: Optional[str] = None  # new, contacted, qualified, proposal, closed
    notes: Optional[str] = None
    score: Optional[int] = None


@router.get("/")
async def list_leads(
      status: Optional[str] = None,
      skip: int = 0,
      limit: int = 20,
      db: AsyncSession = Depends(get_db),
      current_user=Depends(get_current_user)
  ):
        query = select(Contact)
        result = await db.execute(query.offset(skip).limit(limit))
        leads = result.scalars().all()
        return [{"id": str(l.id), "name": f"{l.first_name} {l.last_name}", "email": l.email, "title": l.title} for l in leads]


@router.post("/enrich/{contact_id}")
async def enrich_lead(contact_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      """Trigger Lead Enrichment Agent for a specific contact"""
      result = await db.execute(select(Contact).where(Contact.id == contact_id))
      contact = result.scalar_one_or_none()
      if not contact:
                raise HTTPException(status_code=404, detail="Contact not found")
            # TODO: Call enrichment agent
            return {"message": f"Enrichment triggered for {contact.email}", "contact_id": contact_id, "status": "queued"}
