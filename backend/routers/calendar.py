from backend.tenancy import require_approved_execution
from backend.tenancy import get_workspace_db as get_db
"""Calendar Router - Meeting Scheduling and Google OAuth"""

from datetime import datetime
from typing import Optional
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import Contact, Meeting, Integration
from backend.routers.auth import get_current_user, create_access_token
from backend.security import encrypt_credentials


router = APIRouter()

class MeetingRequest(BaseModel):
    contact_id: UUID
    title: str = "Discovery Call - AI GTM"
    duration_minutes: int = 30
    preferred_date: Optional[str] = None
    notes: Optional[str] = None


@router.post("/book", dependencies=[Depends(require_approved_execution)])
async def book_meeting(
    request: MeetingRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a meeting record."""

    contact = await db.get(Contact, request.contact_id)

    if not contact:
        raise HTTPException(
            status_code=404,
            detail="Contact not found",
        )

    meeting_time = None

    if request.preferred_date:
        try:
            meeting_time = datetime.fromisoformat(
                request.preferred_date
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "preferred_date must be ISO format "
                    "(YYYY-MM-DDTHH:MM:SS)"
                ),
            )

    meeting = Meeting(
        contact_id=contact.id,
        contact_email=contact.email,
        title=request.title,
        duration_minutes=request.duration_minutes,
        meeting_time=meeting_time,
        notes=request.notes,
        status="scheduled",
    )

    db.add(meeting)

    await db.commit()
    await db.refresh(meeting)

    return {
        "message": "Meeting booked successfully",
        "meeting_id": str(meeting.id),
        "contact": contact.email,
        "status": meeting.status,
    }


@router.get("/")
async def list_meetings(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Meeting)
    )

    meetings = result.scalars().all()

    data = []

    for m in meetings:
        data.append(
            {
                "id": str(m.id),
                "contact_id": str(m.contact_id),
                "contact_email": m.contact_email,
                "title": m.title,
                "meeting_time": m.meeting_time,
                "duration_minutes": m.duration_minutes,
                "status": m.status,
                "notes": m.notes,
                "created_at": m.created_at,
            }
        )

    return data


@router.get("/auth")
async def calendar_auth_info():
    return {
        "setup_required": "Google Calendar OAuth2",
        "status": "OAuth endpoints available",
        "start_endpoint": "/api/v1/calendar/oauth/google/start",
        "callback_endpoint": "/api/v1/calendar/oauth/google/callback",
        "next_stage": "Connect Google Calendar credentials",
    }