"""Calendar Router - Google Calendar meeting booking (Step 50-51)"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from backend.routers.auth import get_current_user

router = APIRouter()


class MeetingRequest(BaseModel):
      contact_email: str
      contact_name: str
      title: str = "Discovery Call - AI GTM"
      duration_minutes: int = 30
      preferred_date: Optional[str] = None
      notes: Optional[str] = None


@router.post("/book")
async def book_meeting(request: MeetingRequest, current_user=Depends(get_current_user)):
      """Book a meeting via Google Calendar API"""
      # TODO: Integrate with Google Calendar OAuth2 flow
      # For now returns a mock booking confirmation
      return {
          "message": "Meeting booking queued",
          "contact": request.contact_email,
          "title": request.title,
          "duration": f"{request.duration_minutes} minutes",
          "status": "pending_calendar_auth",
          "next_step": "Complete Google Calendar OAuth at /api/v1/calendar/auth"
      }


@router.get("/auth")
async def calendar_auth_info():
      """Instructions for Google Calendar OAuth setup"""
      return {
          "setup_required": "Google Calendar OAuth2",
          "steps": [
              "1. Create OAuth2 credentials in Google Cloud Console",
              "2. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
              "3. Authorize the app at the OAuth consent screen",
              "4. Calendar bookings will use the authorized token"
          ]
      }
