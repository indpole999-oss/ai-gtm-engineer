from backend.tenancy import get_workspace_db as get_db
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from backend.database import Contact
from backend.routers.auth import get_current_user


router = APIRouter()


# ============================================================
# SCHEMA
# ============================================================

class ContactCreate(BaseModel):
    company_id: str
    first_name: str
    last_name: str
    email: EmailStr
    title: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None


# ============================================================
# CREATE CONTACT
# ============================================================

@router.post("/")
async def create_contact(
    contact: ContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        company_uuid = UUID(contact.company_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid company_id UUID"
        )

    new_contact = Contact(
        company_id=company_uuid,
        first_name=contact.first_name,
        last_name=contact.last_name,
        email=contact.email,
        title=contact.title,
        linkedin_url=contact.linkedin_url,
        phone=contact.phone,
    )

    db.add(new_contact)

    await db.commit()
    await db.refresh(new_contact)

    return {
        "id": str(new_contact.id),
        "company_id": str(new_contact.company_id)
        if new_contact.company_id
        else None,
        "first_name": new_contact.first_name,
        "last_name": new_contact.last_name,
        "email": new_contact.email,
        "title": new_contact.title,
        "linkedin_url": new_contact.linkedin_url,
        "phone": new_contact.phone,
        "message": "Contact created successfully",
    }


# ============================================================
# GET CONTACT BY ID
# ============================================================

@router.get("/{contact_id}")
async def get_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )

    contact = result.scalar_one_or_none()

    if contact is None:
        raise HTTPException(
            status_code=404,
            detail="Contact not found"
        )

    return {
        "id": str(contact.id),
        "company_id": str(contact.company_id)
        if contact.company_id
        else None,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "title": contact.title,
        "linkedin_url": contact.linkedin_url,
        "phone": contact.phone,
        "enriched_data": contact.enriched_data,
        "lead_score": contact.lead_score,
        "priority": contact.priority,
        "insights": contact.insights,
        "enriched_at": contact.enriched_at,
        "created_at": contact.created_at,
    }


# ============================================================
# LIST CONTACTS
# ============================================================

@router.get("/")
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Contact)
    )

    contacts = result.scalars().all()

    return [
        {
            "id": str(contact.id),
            "company_id": str(contact.company_id)
            if contact.company_id
            else None,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "email": contact.email,
            "title": contact.title,
            "linkedin_url": contact.linkedin_url,
            "phone": contact.phone,
            "enriched_data": contact.enriched_data,
            "lead_score": contact.lead_score,
            "priority": contact.priority,
            "insights": contact.insights,
            "enriched_at": contact.enriched_at,
            "created_at": contact.created_at,
        }
        for contact in contacts
    ]