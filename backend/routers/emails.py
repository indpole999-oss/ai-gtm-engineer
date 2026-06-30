"""Email router - send personalized outreach via Resend API"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import httpx

from backend.database import get_db, EmailLog, Contact
from backend.routers.auth import get_current_user
from backend.config import settings

router = APIRouter()


class EmailRequest(BaseModel):
      contact_id: str
      subject: str
      body: str
      personalize: bool = True


async def send_via_resend(to_email: str, subject: str, body: str) -> dict:
      """Send email using Resend API"""
      async with httpx.AsyncClient() as client:
                response = await client.post(
                              "https://api.resend.com/emails",
                              headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                              json={"from": settings.FROM_EMAIL, "to": [to_email], "subject": subject, "html": body}
                          )
            return response.json()


@router.post("/send")
async def send_email(
      request: EmailRequest,
      background_tasks: BackgroundTasks,
      db: AsyncSession = Depends(get_db),
      current_user=Depends(get_current_user)
  ):
        result = await db.execute(select(Contact).where(Contact.id == request.contact_id))
        contact = result.scalar_one_or_none()
        if not contact:
                  raise HTTPException(status_code=404, detail="Contact not found")
              log = EmailLog(contact_id=contact.id, subject=request.subject, body=request.body, status="queued")
    db.add(log)
    await db.flush()
    background_tasks.add_task(send_via_resend, contact.email, request.subject, request.body)
    return {"message": "Email queued", "email_log_id": str(log.id), "to": contact.email}


@router.get("/logs")
async def email_logs(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      result = await db.execute(select(EmailLog).order_by(EmailLog.created_at.desc()).offset(skip).limit(limit))
    logs = result.scalars().all()
    return [{"id": str(l.id), "subject": l.subject, "status": l.status, "created_at": str(l.created_at)} for l in logs]
