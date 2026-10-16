from backend.tenancy import require_approved_execution
from backend.tenancy import get_workspace_db as get_db
"""Leads router - manage leads pipeline"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

from backend.database import Contact
from backend.routers.auth import get_current_user

router = APIRouter()


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    score: Optional[int] = None


# ============================================================
# LIST LEADS
# ============================================================

@router.get("/")
async def list_leads(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Contact))
    contacts = result.scalars().all()

    leads = []

    for c in contacts:

        enriched_data = c.enriched_data or {}

        lead_score = c.lead_score if c.lead_score is not None else 50
        priority = c.priority or "medium"
        insights = c.insights or "Not enriched yet"

        leads.append({
            "id": str(c.id),
            "name": f"{c.first_name} {c.last_name}",
            "email": c.email,
            "title": c.title,
            "lead_score": lead_score,
            "priority": priority,
            "insights": insights,
            "enriched": bool(enriched_data),
            "enriched_at": c.enriched_at,
        })

    return leads


# ============================================================
# ENRICH LEAD
# ============================================================

@router.post("/enrich/{contact_id}", dependencies=[Depends(require_approved_execution)])
async def enrich_lead(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Enrich a contact using the EnrichmentAgent
    and persist the result in the database.
    """

    # --------------------------------------------------------
    # Find contact
    # --------------------------------------------------------

    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )

    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=404,
            detail="Contact not found"
        )

    # --------------------------------------------------------
    # Determine domain
    # --------------------------------------------------------

    domain = None

    if contact.email and "@" in contact.email:
        domain = contact.email.split("@")[1].lower()

    if not domain:
        raise HTTPException(
            status_code=400,
            detail="Unable to determine company domain from contact email"
        )

    # --------------------------------------------------------
    # Call Enrichment Agent
    # --------------------------------------------------------

    try:

        from agents.enrichment_agent import EnrichmentAgent

        agent = EnrichmentAgent()

        enrichment_result = await agent.run(
            task=f"Enrich contact {contact.email}",
            context={
                "domain": domain,
                "email": contact.email,
                "company": None,
            }
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Enrichment agent failed: {str(e)}"
        )

    # --------------------------------------------------------
    # Check result
    # --------------------------------------------------------

    if not enrichment_result:

        raise HTTPException(
            status_code=500,
            detail="Enrichment agent returned no result"
        )

    # --------------------------------------------------------
    # Persist enrichment data
    # --------------------------------------------------------

    contact.enriched_data = enrichment_result
    contact.enriched_at = __import__("datetime").datetime.utcnow()

    # --------------------------------------------------------
    # Basic lead scoring
    # --------------------------------------------------------

    if enrichment_result.get("status") == "completed":

        contact.lead_score = 75
        contact.priority = "high"

        contact.insights = (
            "Lead enriched successfully using external enrichment provider."
        )

    elif enrichment_result.get("status") == "skipped":

        contact.lead_score = 50
        contact.priority = "medium"

        contact.insights = (
            enrichment_result.get(
                "reason",
                "Enrichment provider not configured."
            )
        )

    else:

        contact.lead_score = 50
        contact.priority = "medium"

        contact.insights = (
            "Enrichment attempted but provider returned an error."
        )

    await db.commit()
    await db.refresh(contact)

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {
        "message": "Lead enrichment completed",
        "contact_id": str(contact.id),
        "email": contact.email,
        "status": enrichment_result.get(
            "status",
            "completed"
        ),
        "enrichment": enrichment_result,
        "lead_score": contact.lead_score,
        "priority": contact.priority,
        "insights": contact.insights,
        "enriched_at": contact.enriched_at,
    }