"""Offline HTTP contract tests; these are NOT evidence of a live Google write."""
from datetime import datetime, timedelta
from uuid import UUID

import httpx
import pytest

from backend.database import AsyncSessionLocal, Integration, Meeting, WorkspaceMembership
from backend.security import decrypt_credentials
from test_integration_foundation import configured, fake_google, start  # noqa: F401
from test_workspace_security import signup


@pytest.fixture
def google_wire(monkeypatch):
    state = {"events": {}, "posts": 0, "gets": 0, "mode": "ok", "tokens": []}
    original = httpx.AsyncClient

    def handle(request):
        import json
        assert request.url.host == "www.googleapis.com"
        state["tokens"].append(request.headers["Authorization"])
        if state["mode"] == "unauthorized":
            return httpx.Response(401)
        if request.method == "GET":
            state["gets"] += 1
            event = state["events"].get(request.url.path.split("/")[-1])
            return httpx.Response(200, json=event) if event else httpx.Response(404)
        assert request.method == "POST"
        state["posts"] += 1
        body = json.loads(request.content)
        assert body["attendees"] == []
        assert request.url.params["sendUpdates"] == "none"
        assert body["reminders"] == {"useDefault": False}
        event = dict(body, status="confirmed", etag='"revision-one"',
            htmlLink="https://calendar.google.com/calendar/event?eid=test")
        state["events"][body["id"]] = event
        if state["mode"] == "timeout":
            raise httpx.ReadTimeout("lost response", request=request)
        if state["mode"] == "conflict":
            return httpx.Response(409)
        if state["mode"] == "mismatch":
            event["summary"] = "Changed remotely"
        return httpx.Response(200, json=event)

    monkeypatch.setattr("backend.google_calendar_transport.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    return state


def connected(client):
    headers = signup(client, "calendar-test@example.com")
    state = start(client, headers)
    assert client.get("/api/v1/calendar/oauth/google/callback",
        params={"state": state, "code": "test"}, follow_redirects=False).status_code == 303
    iid = client.get("/api/v1/integrations", headers=headers).json()["integrations"][0]["id"]
    return headers, iid, f"/api/v1/integrations/{iid}/calendar-test-event"


@pytest.mark.parametrize("mode", ["ok", "timeout", "conflict"])
def test_create_persist_reload_and_reuse(client, configured, fake_google, google_wire, mode):
    headers, iid, path = connected(client)
    google_wire["mode"] = mode
    assert client.get(path, headers=headers).json() == {"event": None}
    result = client.post(path, headers=headers)
    assert result.status_code == 200, result.text
    event = result.json()["event"]
    assert event["status"] == "confirmed" and event["attendees"] == []
    assert event["provider_event_id"] == UUID(event["id"]).hex
    assert client.get(path, headers=headers).json()["event"] == event
    assert client.post(path, headers=headers).json()["event"]["provider_event_id"] == event["provider_event_id"]
    assert google_wire["posts"] == 1
    assert len(google_wire["events"]) == 1
    assert google_wire["gets"] == 3
    assert "first-token" not in result.text and "refresh-one" not in result.text

    async def persisted():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]), workspace_role="owner")
            meeting = await db.get(Meeting, UUID(event["id"]))
            assert meeting.google_event_id == event["provider_event_id"]
            assert meeting.contact_id is None and meeting.contact_email == ""
    client.portal.call(persisted)


def test_refresh_is_saved_and_reused(client, configured, fake_google, google_wire):
    headers, iid, path = connected(client)
    async def expire():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]), workspace_role="owner")
            row = await db.get(Integration, UUID(iid))
            row.token_expires_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire)
    assert client.post(path, headers=headers).json()["event"]["status"] == "confirmed"
    assert client.post(path, headers=headers).json()["event"]["status"] == "confirmed"
    assert all(t == "Bearer refreshed-token" for t in google_wire["tokens"])
    assert len([c for c in fake_google if c[0] == "refresh"]) == 1
    async def inspect():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]), workspace_role="owner")
            row = await db.get(Integration, UUID(iid))
            assert decrypt_credentials(row.credentials)["refresh_token"] == "rotated-refresh"
    client.portal.call(inspect)


@pytest.mark.parametrize("change", ["cancelled", "summary", "missing", "metadata"])
def test_remote_changes_never_report_success_or_recreate(client, configured, fake_google, google_wire, change):
    headers, iid, path = connected(client)
    event = client.post(path, headers=headers).json()["event"]
    remote = google_wire["events"][event["provider_event_id"]]
    if change == "cancelled":
        remote["status"] = "cancelled"
    elif change == "summary":
        remote["summary"] = "Not the requested meeting"
    elif change == "metadata":
        remote["extendedProperties"]["private"]["gaps_namespace"] = "other-tenant"
    else:
        google_wire["events"].clear()
    result = client.post(path, headers=headers).json()["event"]
    assert result["status"] == "unverified"
    assert google_wire["posts"] == 1


def test_tenant_and_admin_boundaries_and_reconnect(client, configured, fake_google, google_wire):
    headers, iid, path = connected(client)
    other = signup(client, "other-calendar@example.com")
    assert client.get(path, headers=other).status_code == 404
    assert client.post(path, headers=other).status_code == 404
    assert client.post(path, headers=headers).json()["event"]["status"] == "confirmed"
    state = start(client, headers, f"?integration_id={iid}")
    client.get("/api/v1/calendar/oauth/google/callback", params={"state": state, "code": "test"}, follow_redirects=False)
    assert client.post(path, headers=headers).json()["event"]["status"] == "confirmed"
    assert google_wire["posts"] == 1
    # Reconnect to a different calendar account cannot silently copy the event.
    google_wire["events"].clear()
    state = start(client, headers, f"?integration_id={iid}")
    client.get("/api/v1/calendar/oauth/google/callback", params={"state": state, "code": "test"}, follow_redirects=False)
    assert client.post(path, headers=headers).json()["event"]["status"] == "unverified"
    assert google_wire["posts"] == 1
    async def demote():
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            row = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(headers["X-Workspace-ID"])))
            row.role = "member"
            await db.commit()
    client.portal.call(demote)
    assert client.post(path, headers=headers).status_code == 403


@pytest.mark.parametrize("mode", ["unauthorized", "mismatch"])
def test_failure_is_persisted_not_success(client, configured, fake_google, google_wire, mode):
    headers, iid, path = connected(client)
    google_wire["mode"] = mode
    event = client.post(path, headers=headers).json()["event"]
    assert event["status"] == "unverified" and not event["provider_event_id"]
    assert client.get(path, headers=headers).json()["event"] == event
