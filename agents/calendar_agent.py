
"""
Calendar Agent - Google Calendar and Calendly meeting scheduling

Supports:
- Google Calendar OAuth2 credentials stored in Integration
- Calendly API
"""

import httpx
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import Integration, AsyncSessionLocal
from backend.security import decrypt_credentials
from backend.config import settings


logger = logging.getLogger(__name__)


CALENDAR_PROVIDER = os.getenv("CALENDAR_PROVIDER", "google")

GOOGLE_CALENDAR_CREDENTIALS = os.getenv(
    "GOOGLE_CALENDAR_CREDENTIALS",
    "",
)

GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "primary",
)

CALENDLY_API_KEY = os.getenv(
    "CALENDLY_API_KEY",
    "",
)

CALENDLY_USER_URL = os.getenv(
    "CALENDLY_USER_URL",
    "",
)


class CalendarAgent:
    """Manages meeting scheduling via Google Calendar or Calendly."""

    def __init__(self):
        self.provider = CALENDAR_PROVIDER
        self.google_creds = GOOGLE_CALENDAR_CREDENTIALS
        self.calendar_id = GOOGLE_CALENDAR_ID
        self.calendly_key = CALENDLY_API_KEY

    # ------------------------------------------------------------------
    # Google OAuth2
    # ------------------------------------------------------------------

    async def _get_google_oauth_credentials(
        self,
        user_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ):
        """
        Load Google OAuth2 credentials for the authenticated user.

        Credentials are stored encrypted in Integration.credentials.
        """

        if not user_id:
            logger.error(
                "Google Calendar lookup failed: missing user_id"
            )
            return None

        try:
            user_uuid = UUID(str(user_id))
        except (ValueError, TypeError, AttributeError):
            logger.error(
                "Google Calendar lookup failed: invalid user_id=%r",
                user_id,
            )
            return None

        try:

            async def lookup(session: AsyncSession):
                result = await session.execute(
                    select(Integration).where(
                        Integration.user_id == user_uuid,
                        Integration.category == "calendar",
                        Integration.provider == "google",
                        Integration.status == "connected",
                    )
                )

                return result.scalar_one_or_none()

            if db is not None:
                integration = await lookup(db)
            else:
                async with AsyncSessionLocal() as session:
                    integration = await lookup(session)

            if not integration:
                logger.error(
                    "GOOGLE CALENDAR INTEGRATION NOT FOUND: "
                    "user_id=%s category=calendar provider=google "
                    "status=connected",
                    user_uuid,
                )
                return None

            logger.info(
                "GOOGLE CALENDAR INTEGRATION FOUND: "
                "id=%s user_id=%s",
                integration.id,
                integration.user_id,
            )

            token_data = decrypt_credentials(
                integration.credentials
            )

            if not isinstance(token_data, dict):
                logger.error(
                    "Google Calendar credentials are not a dictionary"
                )
                return None

            access_token = token_data.get("access_token")

            if not access_token:
                logger.error(
                    "Google Calendar integration found but "
                    "access_token is missing"
                )
                return None

            from google.oauth2.credentials import Credentials

            credentials = Credentials(
                token=access_token,
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get(
                    "token_uri",
                    "https://oauth2.googleapis.com/token",
                ),
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=token_data.get("scopes"),
            )

            if token_data.get("expiry"):
                try:
                    credentials.expiry = datetime.fromisoformat(
                        str(token_data["expiry"]).replace(
                            "Z",
                            "+00:00",
                        )
                    )
                except (TypeError, ValueError):
                    logger.warning(
                        "Could not parse Google OAuth expiry"
                    )

            return credentials

        except Exception as exc:
            logger.exception(
                "Failed to load Google OAuth credentials: %s",
                exc,
            )
            return None

    async def _get_google_service(
        self,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ):
        """
        Build Google Calendar API service.

        Preferred:
            OAuth credentials stored in Integration.

        Legacy fallback:
            GOOGLE_CALENDAR_CREDENTIALS service-account configuration.
        """

        try:
            from googleapiclient.discovery import build

            credentials = await self._get_google_oauth_credentials(
                user_id=user_id,
                db=db,
            )

            if credentials:

                if credentials.expired and credentials.refresh_token:
                    from google.auth.transport.requests import Request

                    credentials.refresh(Request())

                if not credentials.valid:
                    logger.error(
                        "Google OAuth credentials are invalid"
                    )
                    return None

                return build(
                    "calendar",
                    "v3",
                    credentials=credentials,
                )

            # Legacy service-account fallback.
            if self.google_creds and settings.ALLOW_LEGACY_ENV_CREDENTIALS:
                import json
                from google.oauth2 import service_account

                scopes = [
                    "https://www.googleapis.com/auth/calendar"
                ]

                if os.path.exists(self.google_creds):
                    service_account_creds = (
                        service_account.Credentials
                        .from_service_account_file(
                            self.google_creds,
                            scopes=scopes,
                        )
                    )
                else:
                    creds_info = json.loads(
                        self.google_creds
                    )

                    service_account_creds = (
                        service_account.Credentials
                        .from_service_account_info(
                            creds_info,
                            scopes=scopes,
                        )
                    )

                return build(
                    "calendar",
                    "v3",
                    credentials=service_account_creds,
                )

            return None

        except ImportError:
            logger.error(
                "Google Calendar dependencies are missing. "
                "Install google-api-python-client google-auth"
            )
            raise

        except Exception as exc:
            logger.exception(
                "Google Calendar authentication failed: %s",
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Google Calendar event creation
    # ------------------------------------------------------------------

    async def create_google_event(
        self,
        meeting: Dict,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict:
        """Create a Google Calendar event."""

        start_dt = meeting.get("start_time")

        if not start_dt:
            return {
                "status": "skipped",
                "reason": "Meeting start_time is required",
            }

        try:
            if isinstance(start_dt, str):
                parsed_start = datetime.fromisoformat(
                    start_dt.replace("Z", "+00:00")
                )
            else:
                parsed_start = start_dt

            duration = int(
                meeting.get(
                    "duration_minutes",
                    30,
                )
            )

            end_dt = meeting.get("end_time")

            if end_dt:
                if isinstance(end_dt, str):
                    parsed_end = datetime.fromisoformat(
                        end_dt.replace("Z", "+00:00")
                    )
                else:
                    parsed_end = end_dt
            else:
                parsed_end = parsed_start + timedelta(
                    minutes=duration
                )

            timezone_str = meeting.get(
                "timezone",
                "UTC",
            )

            service = await self._get_google_service(
                user_id=user_id,
                db=db,
            )

            if not service:
                return {
                    "status": "skipped",
                    "reason": (
                        "No connected Google Calendar integration"
                    ),
                }

            event = {
                "summary": meeting.get(
                    "title",
                    "Meeting",
                ),
                "description": meeting.get(
                    "description",
                    "",
                ),
                "start": {
                    "dateTime": parsed_start.isoformat(),
                    "timeZone": timezone_str,
                },
                "end": {
                    "dateTime": parsed_end.isoformat(),
                    "timeZone": timezone_str,
                },
                "attendees": [
                    {"email": email}
                    for email in meeting.get(
                        "attendees",
                        [],
                    )
                    if email
                ],
                "reminders": {
                    "useDefault": True
                },
            }

            if meeting.get("add_meet_link", True):
                event["conferenceData"] = {
                    "createRequest": {
                        "requestId": (
                            f"gtm-{datetime.now().timestamp()}"
                        ),
                        "conferenceSolutionKey": {
                            "type": "hangoutsMeet"
                        },
                    }
                }

            conference_version = (
                1
                if "conferenceData" in event
                else 0
            )

            created = (
                service.events()
                .insert(
                    calendarId=meeting.get(
                        "calendar_id",
                        self.calendar_id,
                    ),
                    body=event,
                    conferenceDataVersion=conference_version,
                    sendUpdates="all",
                )
                .execute()
            )

            conference_data = created.get(
                "conferenceData",
                {},
            )

            meet_link = None

            for entry_point in conference_data.get(
                "entryPoints",
                [],
            ):
                if entry_point.get(
                    "entryPointType"
                ) == "video":
                    meet_link = entry_point.get("uri")
                    break

            return {
                "provider": "google_calendar",
                "event_id": created.get("id"),
                "html_link": created.get("htmlLink"),
                "meet_link": meet_link,
                "status": "created",
            }

        except Exception as exc:
            logger.exception(
                "Google Calendar event creation failed: %s",
                exc,
            )

            return {
                "status": "error",
                "reason": str(exc),
            }

    # ------------------------------------------------------------------
    # Google Calendar availability
    # ------------------------------------------------------------------

    async def get_free_slots(
        self,
        date: str,
        duration_minutes: int = 30,
        timezone_str: str = "UTC",
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> List[Dict]:

        service = await self._get_google_service(
            user_id=user_id,
            db=db,
        )

        if not service:
            return []

        day_start = datetime.fromisoformat(
            f"{date}T09:00:00"
        )

        day_end = datetime.fromisoformat(
            f"{date}T18:00:00"
        )

        freebusy = (
            service.freebusy()
            .query(
                body={
                    "timeMin": day_start.isoformat(),
                    "timeMax": day_end.isoformat(),
                    "timeZone": timezone_str,
                    "items": [
                        {
                            "id": self.calendar_id
                        }
                    ],
                }
            )
            .execute()
        )

        busy = freebusy["calendars"][
            self.calendar_id
        ]["busy"]

        slots = []
        current = day_start

        for busy_period in busy:
            busy_start = datetime.fromisoformat(
                busy_period["start"].replace(
                    "Z",
                    "",
                )
            )

            if (
                current
                + timedelta(
                    minutes=duration_minutes
                )
                <= busy_start
            ):
                slots.append(
                    {
                        "start": current.isoformat(),
                        "end": (
                            current
                            + timedelta(
                                minutes=duration_minutes
                            )
                        ).isoformat(),
                    }
                )

            current = max(
                current,
                datetime.fromisoformat(
                    busy_period["end"].replace(
                        "Z",
                        "",
                    )
                ),
            )

        if (
            current
            + timedelta(
                minutes=duration_minutes
            )
            <= day_end
        ):
            slots.append(
                {
                    "start": current.isoformat(),
                    "end": (
                        current
                        + timedelta(
                            minutes=duration_minutes
                        )
                    ).isoformat(),
                }
            )

        return slots[:5]

    # ------------------------------------------------------------------
    # Calendly
    # ------------------------------------------------------------------

    async def get_calendly_event_types(
        self,
    ) -> List[Dict]:

        if not self.calendly_key:
            return []

        async with httpx.AsyncClient(
            timeout=30
        ) as client:

            resp = await client.get(
                "https://api.calendly.com/event_types",
                headers={
                    "Authorization": (
                        f"Bearer {self.calendly_key}"
                    )
                },
                params={
                    "user": CALENDLY_USER_URL,
                    "active": True,
                },
            )

            resp.raise_for_status()

            data = resp.json()

            return [
                {
                    "name": event_type["name"],
                    "link": event_type["scheduling_url"],
                    "duration": event_type["duration"],
                }
                for event_type in data.get(
                    "collection",
                    [],
                )
            ]

    async def generate_booking_link(
        self,
        event_type_name: str = "15 Minute Meeting",
    ) -> Dict:

        event_types = await self.get_calendly_event_types()

        for event_type in event_types:
            if (
                event_type_name.lower()
                in event_type["name"].lower()
            ):
                return {
                    "booking_link": event_type["link"],
                    "duration": event_type["duration"],
                    "status": "found",
                }

        if event_types:
            return {
                "booking_link": event_types[0]["link"],
                "duration": event_types[0]["duration"],
                "status": "found_default",
            }

        return {
            "status": "not_found",
            "reason": "No Calendly event types found",
        }

    # ------------------------------------------------------------------
    # Unified scheduling
    # ------------------------------------------------------------------

    async def book_meeting(
        self,
        meeting: Dict,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict:

        if self.provider == "google":
            return await self.create_google_event(
                meeting=meeting,
                user_id=user_id,
                db=db,
            )

        if (
            self.provider == "calendly"
            and self.calendly_key
        ):
            return await self.generate_booking_link(
                meeting.get(
                    "event_type",
                    "15 Minute Meeting",
                )
            )

        return {
            "status": "skipped",
            "reason": "No calendar provider configured",
        }

    # ------------------------------------------------------------------
    # Agent entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:

        context = context or {}

        action = context.get(
            "action",
            "book_meeting",
        )

        # Workflow Engine supplies a flat context.
        # Support both nested meeting context and flat context.
        meeting = context.get(
            "meeting",
            context,
        )

        user_id = context.get("user_id")

        # CalendarAgent should not depend on a database session
        # being injected into workflow context.
        db = None

        logger.info(
            "CALENDAR DEBUG: user_id=%s",
            user_id,
        )

        if action == "book_meeting":
            return await self.book_meeting(
                meeting=meeting,
                user_id=user_id,
                db=db,
            )

        if action == "get_slots":
            date = context.get("date")

            duration = context.get(
                "duration_minutes",
                30,
            )

            timezone_str = context.get(
                "timezone",
                "UTC",
            )

            if not date:
                return {
                    "status": "error",
                    "reason": "Date required",
                }

            slots = await self.get_free_slots(
                date=date,
                duration_minutes=duration,
                timezone_str=timezone_str,
                user_id=user_id,
                db=db,
            )

            return {
                "date": date,
                "available_slots": slots,
                "status": "success",
            }

        if action == "get_booking_link":
            event_type = context.get(
                "event_type",
                "15 Minute Meeting",
            )

            return await self.generate_booking_link(
                event_type
            )

        return {
            "status": "error",
            "reason": f"Unknown action: {action}",
        }
