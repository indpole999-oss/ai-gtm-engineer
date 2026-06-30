"""Contacts router - CRUD for people/leads contacts"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from backend.database import get_db, Contact
from backend.routers.auth import get_current_user

router = APIRouter()


class ContactCreate(BaseModel):
      first_name: str
      last_name: Optional[str] = None
      email: Optional[EmailStr] = None
      title: Optional[str] = None
      linkedin_url: Optional[str] = None
      company_id: Optional[str] = None


@router.get("")
async def list_contacts(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      result = await db.execute(select(Contact).offset(skip).limit(limit))
      contacts = result.scalars().all()
      return [{"id": str(c.id), "name": f"{c.first_name} {c.last_name}", "email": c.email, "title": c.title} for c in contacts]


@router.post("", status_code=201)
async def create_contact(data: ContactCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      contact = Contact(**data.model_dump())
      db.add(contact)
      await db.flush()
      return {"id": str(contact.id), "email": contact.email, "message": "Contact created"}


@router.get("/{contact_id}")
async def get_contact(contact_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      result = await db.execute(select(Contact).where(Contact.id == contact_id))
      contact = result.scalar_one_or_none()
      if not contact:
                raise HTTPException(status_code=404, detail="Contact not found")
            return {"id": str(contact.id), "first_name": contact.first_name, "last_name": contact.last_name, "email": contact.email, "title": contact.title, "linkedin_url": contact.linkedin_url}
