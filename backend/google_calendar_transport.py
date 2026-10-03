"""Create-only Calendar transport with stable IDs and authoritative readback.

No update, delete, conference creation, or arbitrary HTTP destinations are exposed.
"""
from datetime import datetime
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx

from backend.planning_service import digest
from backend.providers import ProviderError


def event_fingerprint(event):
    """Google may normalize offsets and omit an empty attendees array."""
    return digest({
        "summary": event.get("summary"),
        "start": datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00")).timestamp(),
        "end": datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00")).timestamp(),
        "attendees": sorted(a["email"].lower() for a in event.get("attendees", [])),
    })


class GoogleCalendarTransport:
    durable_idempotency = True
    # Create-only: existing events are never overwritten, including on a retry.
    atomic_versions = True

    def __init__(self, integration, credentials):
        self.namespace = str(integration.id)
        self.calendar = str((integration.config or {}).get("calendar_id") or "primary")
        self.token = credentials.get("access_token")
        self.base = "https://www.googleapis.com/calendar/v3/calendars/" + quote(self.calendar, safe="") + "/events"

    async def request(self, method, suffix="", **kwargs):
        if not self.token:
            raise ProviderError("reconnect_required")
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.request(method, self.base + suffix,
                    headers={"Authorization": "Bearer " + self.token}, **kwargs)
        except httpx.HTTPError:
            raise ProviderError("provider_outcome_unknown") from None
        if response.status_code in (401, 403):
            raise ProviderError("reconnect_required")
        if method == "GET" and response.status_code == 404:
            return None
        if response.status_code == 409:
            raise ProviderError("remote_conflict")
        if not 200 <= response.status_code < 300:
            raise ProviderError("provider_unavailable")
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except ValueError:
            raise ProviderError("provider_not_confirmed") from None

    def receipt(self, event, namespace, key):
        try:
            meta = event.get("extendedProperties", {}).get("private", {})
            if (event.get("status") != "confirmed" or event.get("id") != UUID(key).hex
                    or not event.get("etag") or meta.get("gaps_namespace") != namespace
                    or meta.get("gaps_key") != key or not meta.get("gaps_request")
                    or meta.get("gaps_event") != event_fingerprint(event)):
                raise ValueError()
            link = event.get("htmlLink", "")
            parsed = urlparse(link)
            if parsed.scheme != "https" or parsed.hostname not in {"www.google.com", "calendar.google.com"}:
                link = None
            return {"status": "confirmed", "id": event["id"], "version": event["etag"],
                "request_hash": meta["gaps_request"], "html_link": link,
                "summary": event.get("summary"), "start": event["start"], "end": event["end"]}
        except (KeyError, TypeError, ValueError):
            raise ProviderError("provider_not_confirmed") from None

    async def lookup(self, namespace, key):
        if namespace != self.namespace:
            raise ProviderError("provider_identity_mismatch")
        event = await self.request("GET", "/" + UUID(key).hex)
        return self.receipt(event, namespace, key) if event is not None else None

    async def fetch(self, *args):
        raise ProviderError("calendar_updates_not_supported")

    async def apply(self, namespace, key, request):
        props = dict(request["properties"])
        if (namespace != self.namespace or request["object_type"] != "events"
                or request["expected_version"] is not None
                or request["external_id"] != UUID(key).hex or props.get("id") != UUID(key).hex
                or props.pop("calendar_id", None) != self.calendar):
            raise ProviderError("provider_identity_mismatch")
        props["extendedProperties"] = {"private": {"gaps_namespace": namespace, "gaps_key": key,
            "gaps_request": digest(request), "gaps_event": event_fingerprint(props)}}
        # Test events have no attendees and no notifications. Reviewed customer
        # bookings use their explicit attendees through the existing approval path.
        props["reminders"] = {"useDefault": False}
        try:
            await self.request("POST", json=props,
                params={"sendUpdates": "all" if props.get("attendees") else "none"})
        except ProviderError as error:
            if error.code not in {"remote_conflict", "provider_outcome_unknown"}:
                raise
            # A lost insert response must reconcile the SAME ID, never a new one.
        result = await self.lookup(namespace, key)
        if result is None or result["request_hash"] != digest(request):
            raise ProviderError("provider_not_confirmed")
        return result
