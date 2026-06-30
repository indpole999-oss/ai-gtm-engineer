"""
Calendar Agent - Google Calendar and Calendly meeting scheduling
Steps 66-70: Meeting booking, calendar availability, invite management
"""
import httpx
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Calendar provider config
CALENDAR_PROVIDER = os.getenv("CALENDAR_PROVIDER", "google")  # google | calendly
GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")  # JSON string or file path
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
CALENDLY_API_KEY = os.getenv("CALENDLY_API_KEY", "")
CALENDLY_USER_URL = os.getenv("CALENDLY_USER_URL", "")  # e.g. https://api.calendly.com/users/xxx


class CalendarAgent:
  """Manages meeting scheduling via Google Calendar or Calendly"""

  def __init__(self):
    self.provider = CALENDAR_PROVIDER
    self.google_creds = GOOGLE_CALENDAR_CREDENTIALS
    self.calendar_id = GOOGLE_CALENDAR_ID
    self.calendly_key = CALENDLY_API_KEY

  # ── Google Calendar ───────────────────────────────────────────────────────

  def _get_google_service(self):
    """Build Google Calendar service using service account credentials"""
    try:
      import json
      from google.oauth2 import service_account
      from googleapiclient.discovery import build

      SCOPES = ["https://www.googleapis.com/auth/calendar"]
      if os.path.exists(self.google_creds):
        creds = service_account.Credentials.from_service_account_file(self.google_creds, scopes=SCOPES)
      else:
        creds_info = json.loads(self.google_creds)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
      return build("calendar", "v3", credentials=creds)
    except ImportError:
      logger.error("google-api-python-client not installed. Run: pip install google-api-python-client google-auth")
      raise
    except Exception as e:
      logger.error(f"Google Calendar auth failed: {e}")
      raise

  def create_google_event(self, meeting: Dict) -> Dict:
    """Create a Google Calendar event/meeting invite"""
    service = self._get_google_service()
    start_dt = meeting.get("start_time")  # ISO format string
    end_dt = meeting.get("end_time") or (
      datetime.fromisoformat(start_dt) + timedelta(minutes=meeting.get("duration_minutes", 30))
    ).isoformat()

    event = {
      "summary": meeting.get("title", "Meeting"),
      "description": meeting.get("description", ""),
      "start": {"dateTime": start_dt, "timeZone": meeting.get("timezone", "UTC")},
      "end": {"dateTime": end_dt if isinstance(end_dt, str) else end_dt.isoformat(), "timeZone": meeting.get("timezone", "UTC")},
      "attendees": [{"email": e} for e in meeting.get("attendees", [])],
      "conferenceData": {
        "createRequest": {"requestId": f"gtm-{datetime.now().timestamp()}", "conferenceSolutionKey": {"type": "hangoutsMeet"}}
      } if meeting.get("add_meet_link", True) else None,
      "reminders": {"useDefault": True}
    }
    # Remove None conferenceData
    if event["conferenceData"] is None:
      del event["conferenceData"]
      conference_version = 0
    else:
      conference_version = 1

    created = service.events().insert(
      calendarId=self.calendar_id,
      body=event,
      conferenceDataVersion=conference_version,
      sendUpdates="all"
    ).execute()

    return {
      "provider": "google_calendar",
      "event_id": created.get("id"),
      "html_link": created.get("htmlLink"),
      "meet_link": created.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri"),
      "status": "created"
    }

  def get_free_slots(self, date: str, duration_minutes: int = 30, timezone_str: str = "UTC") -> List[Dict]:
    """Get available time slots for a given date from Google Calendar"""
    service = self._get_google_service()
    day_start = datetime.fromisoformat(f"{date}T09:00:00")
    day_end = datetime.fromisoformat(f"{date}T18:00:00")

    freebusy = service.freebusy().query(body={
      "timeMin": day_start.isoformat() + "Z",
      "timeMax": day_end.isoformat() + "Z",
      "timeZone": timezone_str,
      "items": [{"id": self.calendar_id}]
    }).execute()

    busy = freebusy["calendars"][self.calendar_id]["busy"]
    # Build free slots
    slots = []
    current = day_start
    for busy_period in busy:
      busy_start = datetime.fromisoformat(busy_period["start"].replace("Z", ""))
      if current + timedelta(minutes=duration_minutes) <= busy_start:
        slots.append({"start": current.isoformat(), "end": (current + timedelta(minutes=duration_minutes)).isoformat()})
      current = max(current, datetime.fromisoformat(busy_period["end"].replace("Z", "")))
    # Check remaining time
    if current + timedelta(minutes=duration_minutes) <= day_end:
      slots.append({"start": current.isoformat(), "end": (current + timedelta(minutes=duration_minutes)).isoformat()})
    return slots[:5]  # Return max 5 slots

  # ── Calendly ──────────────────────────────────────────────────────────────────

  async def get_calendly_event_types(self) -> List[Dict]:
    """Get available Calendly event types for the user"""
    if not self.calendly_key:
      return []
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.get(
        "https://api.calendly.com/event_types",
        headers={"Authorization": f"Bearer {self.calendly_key}"},
        params={"user": CALENDLY_USER_URL, "active": True}
      )
      data = resp.json()
      return [
        {"name": e["name"], "link": e["scheduling_url"], "duration": e["duration"]}
        for e in data.get("collection", [])
      ]

  async def generate_booking_link(self, event_type_name: str = "15 Minute Meeting") -> Dict:
    """Get a Calendly booking link for the given event type"""
    event_types = await self.get_calendly_event_types()
    for et in event_types:
      if event_type_name.lower() in et["name"].lower():
        return {"booking_link": et["link"], "duration": et["duration"], "status": "found"}
    if event_types:
      return {"booking_link": event_types[0]["link"], "duration": event_types[0]["duration"], "status": "found_default"}
    return {"status": "not_found", "reason": "No Calendly event types found"}

  # ── Unified Scheduling ───────────────────────────────────────────────────────

  async def book_meeting(self, meeting: Dict) -> Dict:
    """Book a meeting via configured provider"""
    if self.provider == "google" and self.google_creds:
      return self.create_google_event(meeting)
    elif self.provider == "calendly" and self.calendly_key:
      return await self.generate_booking_link(meeting.get("event_type", "15 Minute Meeting"))
    return {"status": "skipped", "reason": "No calendar provider configured"}

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    action = context.get("action", "book_meeting") if context else "book_meeting"
    meeting = context.get("meeting", {}) if context else {}

    if action == "book_meeting":
      return await self.book_meeting(meeting)
    elif action == "get_slots":
      date = context.get("date") if context else None
      duration = context.get("duration_minutes", 30) if context else 30
      if date and self.google_creds:
        slots = self.get_free_slots(date, duration)
        return {"date": date, "available_slots": slots, "status": "success"}
      return {"status": "error", "reason": "Date required or Google Calendar not configured"}
    elif action == "get_booking_link":
      event_type = context.get("event_type", "15 Minute Meeting") if context else "15 Minute Meeting"
      return await self.generate_booking_link(event_type)

    return {"status": "error", "reason": f"Unknown action: {action}"}
