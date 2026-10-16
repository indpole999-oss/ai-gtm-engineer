"""Explicit admin-authorized, attendee-free connection verification.

Uses the existing Meeting table; never creates customer intent or pipeline history.
One stable test event per connection is retained across refreshes and retries.
"""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid5

from sqlalchemy import select

from backend.database import Meeting, Workspace
from backend import integration_service, outcome_providers
from backend.outcome_service import healthy, binding
from backend.planning_service import digest
from backend.providers import ProviderError


def meeting_id(integration_id):
    return uuid5(integration_id, "gaps-calendar-verification-v1")


def response(row):
    if row is None:
        return {"event": None}
    data = json.loads(row.notes)
    return {"event": {"id": str(row.id), "title": row.title, "status": row.status,
        "provider_event_id": row.google_event_id, "start": data["request"]["properties"]["start"],
        "end": data["request"]["properties"]["end"], "receipt": data.get("receipt"),
        "verified_at": data.get("verified_at"), "last_error": data.get("last_error"),
        "attendees": [], "integration_id": data["integration_id"]}}


async def run(db, ctx, integration_id):
    ctx.require("owner", "admin")
    await db.scalar(select(Workspace).where(Workspace.id == ctx.workspace_id).with_for_update())
    integration = await healthy(db, integration_id, "calendar_schedule")
    identity = meeting_id(integration_id)
    row = await db.get(Meeting, identity)
    generation = await binding(db, integration)
    if row is None:
        start = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0)
        payload = {"event_id": identity.hex, "duplicate_key": str(identity),
            "calendar_id": (integration.config or {}).get("calendar_id") or "primary",
            "title": "GAPS AI — test calendar connection", "attendees": [],
            "start": start.isoformat(), "end": (start + timedelta(minutes=10)).isoformat(), "timezone": "UTC"}
        request = outcome_providers.GoogleCalendarAdapter(None).encode(payload)
        row = Meeting(id=identity, title=payload["title"], contact_email="", status="pending",
            meeting_time=start.replace(tzinfo=None), duration_minutes=10,
            notes=json.dumps({"integration_id": str(integration_id), "binding": generation, "request": request}))
        db.add(row)
        await db.commit()  # Intent is durable before the first external call.
        integration = await healthy(db, integration_id, "calendar_schedule")
        await db.refresh(row, with_for_update=True)
    data = json.loads(row.notes)
    connection_changed = data["binding"] != await binding(db, integration)
    request = data["request"]
    try:
        credentials = await integration_service.refresh_if_needed(db, integration, ctx.user_id)
        transport = outcome_providers.adapter_for(integration, credentials).transport
        receipt = await transport.lookup(str(integration_id), str(identity))
        if receipt is None:
            if connection_changed:
                raise ProviderError("calendar_connection_changed")
            # Never recreate a previously confirmed event that was removed remotely.
            if row.google_event_id or row.meeting_time <= datetime.utcnow():
                raise ProviderError("calendar_event_missing")
            receipt = await transport.apply(str(integration_id), str(identity), request)
        if (receipt.get("status") != "confirmed" or receipt.get("id") != identity.hex
                or receipt.get("request_hash") != digest(request) or not receipt.get("version")):
            raise ProviderError("provider_not_confirmed")
        row.status, row.google_event_id = "confirmed", receipt["id"]
        data.update(receipt=receipt, binding=await binding(db, integration),
            verified_at=datetime.now(timezone.utc).isoformat(), last_error=None)
        integration_service.audit(db, integration, ctx.user_id, "calendar_test_event_verified")
    except ProviderError as error:
        row.status = "unverified"
        data["last_error"] = error.code
        if error.code == "reconnect_required":
            integration.status, integration.health, integration.reconnect_required = "error", "reconnect_required", True
        integration_service.audit(db, integration, ctx.user_id, "calendar_test_event_unverified")
    row.notes = json.dumps(data)
    await db.commit()
    return response(row)
