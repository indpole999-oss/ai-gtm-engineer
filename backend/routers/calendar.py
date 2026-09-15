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
from backend.database import get_db, Contact, Meeting, Integration
from backend.routers.auth import get_current_user, create_access_token
from backend.security import encrypt_credentials


router = APIRouter()

GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]

# Temporary server-side storage for Google OAuth PKCE verifiers.
# This is suitable for the current single-process development setup.
GOOGLE_OAUTH_VERIFIERS = {}


class MeetingRequest(BaseModel):
    contact_id: UUID
    title: str = "Discovery Call - AI GTM"
    duration_minutes: int = 30
    preferred_date: Optional[str] = None
    notes: Optional[str] = None


def _google_oauth_client_config():
    """
    Build the Google OAuth client configuration from application settings.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured: GOOGLE_CLIENT_ID is missing",
        )

    if not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured: GOOGLE_CLIENT_SECRET is missing",
        )

    if not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured: GOOGLE_REDIRECT_URI is missing",
        )

    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                settings.GOOGLE_REDIRECT_URI
            ],
        }
    }


def _create_google_oauth_flow(state: Optional[str] = None):
    """
    Create a Google OAuth authorization-code flow.
    """
    return Flow.from_client_config(
        _google_oauth_client_config(),
        scopes=GOOGLE_CALENDAR_SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


@router.get("/oauth/google/start")
async def google_oauth_start(
    current_user=Depends(get_current_user),
):
    """
    Start Google Calendar OAuth for the authenticated user.
    """
    state = create_access_token(
        {
            "sub": str(current_user.id),
            "purpose": "google_calendar_oauth",
        }
    )

    flow = _create_google_oauth_flow(state=state)

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    # authorization_url() generates a PKCE code_verifier internally.
    # Store that verifier so the callback can use the exact same verifier.
    GOOGLE_OAUTH_VERIFIERS[state] = flow.code_verifier

    return {
        "authorization_url": authorization_url,
        "provider": "google",
        "status": "authorization_required",
    }


@router.get("/oauth/google/callback")
async def google_oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google's OAuth callback and securely store the resulting tokens.
    """
    try:
        payload = jwt.decode(
            state,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except jwt.PyJWTError:
        GOOGLE_OAUTH_VERIFIERS.pop(state, None)
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state",
        )

    if payload.get("purpose") != "google_calendar_oauth":
        GOOGLE_OAUTH_VERIFIERS.pop(state, None)
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    user_id = payload.get("sub")

    if not user_id:
        GOOGLE_OAUTH_VERIFIERS.pop(state, None)
        raise HTTPException(
            status_code=400,
            detail="OAuth state does not contain a valid user",
        )

    # Retrieve the exact PKCE verifier created during the start request.
    # Remove it immediately because it is single-use.
    code_verifier = GOOGLE_OAUTH_VERIFIERS.pop(state, None)

    if not code_verifier:
        raise HTTPException(
            status_code=400,
            detail="OAuth PKCE verifier is missing or expired",
        )

    try:
        flow = _create_google_oauth_flow(state=state)

        # Restore the original PKCE verifier before exchanging the code.
        flow.code_verifier = code_verifier

        flow.fetch_token(code=code)
        credentials = flow.credentials

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth token exchange failed: {str(exc)}",
        )

    if not credentials.token:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth did not return an access token",
        )

    token_data = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "scopes": list(
            credentials.scopes or GOOGLE_CALENDAR_SCOPES
        ),
        "expiry": (
            credentials.expiry.isoformat()
            if credentials.expiry
            else None
        ),
    }

    encrypted_credentials = encrypt_credentials(token_data)

    result = await db.execute(
        select(Integration).where(
            Integration.user_id == UUID(user_id),
            Integration.category == "calendar",
            Integration.provider == "google",
        )
    )

    integration = result.scalar_one_or_none()

    if integration:
        # Google may omit refresh_token when one already exists.
        # Preserve the existing refresh token in that situation.
        if (
            not token_data["refresh_token"]
            and integration.credentials
        ):
            try:
                from backend.security import decrypt_credentials

                existing_credentials = decrypt_credentials(
                    integration.credentials
                )

                if existing_credentials.get("refresh_token"):
                    token_data["refresh_token"] = (
                        existing_credentials["refresh_token"]
                    )

                    encrypted_credentials = encrypt_credentials(
                        token_data
                    )

            except Exception:
                pass

        integration.credentials = encrypted_credentials
        integration.config = {
            "calendar_id": "primary"
        }
        integration.auth_type = "oauth2"
        integration.status = "connected"
        integration.last_connected_at = datetime.utcnow()
        integration.last_error = None

    else:
        integration = Integration(
            user_id=UUID(user_id),
            category="calendar",
            provider="google",
            auth_type="oauth2",
            credentials=encrypted_credentials,
            config={
                "calendar_id": "primary"
            },
            status="connected",
            last_connected_at=datetime.utcnow(),
            last_error=None,
        )

        db.add(integration)

    await db.commit()
    await db.refresh(integration)

    return {
        "message": "Google Calendar connected successfully",
        "provider": "google",
        "integration_id": str(integration.id),
        "status": integration.status,
    }


@router.post("/book")
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