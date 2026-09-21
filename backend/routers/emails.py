from backend.tenancy import require_approved_execution
from backend.tenancy import get_workspace_db as get_db
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from backend.database import Contact, EmailLog
from backend.routers.auth import get_current_user

router = APIRouter()


class EmailSendRequest(BaseModel):
    contact_id: UUID
    subject: str
    body: str


@router.post("/send", dependencies=[Depends(require_approved_execution)])
async def send_email(
    request: EmailSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Find the contact
    result = await db.execute(
        select(Contact).where(Contact.id == request.contact_id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        return {"error": "Contact not found"}

    # Save email log (mock send)
    email = EmailLog(
        contact_id=contact.id,
        subject=request.subject,
        body=request.body,
        status="sent",
        sent_at=datetime.utcnow(),
    )

    db.add(email)
    await db.commit()
    await db.refresh(email)

    return {
        "message": "Email sent successfully",
        "email_id": str(email.id),
        "recipient": contact.email,
        "status": email.status,
    }


@router.get("/")
async def get_email_logs(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(EmailLog))
    emails = result.scalars().all()

    return [
        {
            "id": str(email.id),
            "subject": email.subject,
            "status": email.status,
            "sent_at": email.sent_at,
        }
        for email in emails
    ]