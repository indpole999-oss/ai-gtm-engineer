"""One continuous API journey with isolated fake providers, never live success."""
from datetime import datetime, timezone, timedelta
from test_workspace_security import signup, company
from test_research import published, fake_research  # noqa: F401
from test_outreach import provider, post, approve_draft, get_message  # noqa: F401
from test_inbox import ingest, event
from test_outcomes import transport, integration, run, pipelines, create, get_action  # noqa: F401
from test_planning_execution import approve
from test_insights import query


def test_continuous_approved_customer_journey(client, fake_research, provider, transport):
    a = signup(client, "journey@example.com")
    brain, account = published(client, a), company(client, a)
    calendar_id = integration(client, a, "calendar", "google")
    crm_id = integration(client, a)
    objective = "Find one US B2B SaaS company that matches our ICP and prepare personalized outreach for the best RevOps buyer."
    goal = client.post("/api/v1/gtm/goals", headers=a, json={"objective": objective, "brain_version_id": brain["id"], "targets": [{"company_id": account["id"], "source_urls": ["https://example.com/"]}]}).json()
    plan = client.post(f"/api/v1/gtm/goals/{goal['id']}/plans", headers=a, json={"mode": "research_template"}).json()
    assert not run(client, a)
    cycle = approve(client, a, plan)
    assert run(client, a)
    state = client.get(f"/api/v1/gtm/cycles/{cycle['id']}", headers=a).json()
    assert state["status"] == "completed"
    job_id = state["steps"][0]["output"]["research_job_id"]
    research = client.get("/api/v1/research/jobs/" + job_id, headers=a).json()
    assert research["claims"] and research["intelligence"]["buyers"]
    assert research["intelligence"]["buyers"][0]["verification_status"] == "unknown"
    contact = client.post("/api/v1/contacts/", headers=a, json={"company_id": account["id"], "first_name": "Jane", "last_name": "Buyer", "email": "jane@example.com"}).json()
    campaign = post(client, a, "/campaigns", {"name": "Journey"})
    sequence = post(client, a, "/sequences", {"name": "Journey", "campaign_id": campaign["id"]})
    version = post(client, a, f"/sequences/{sequence['id']}/versions", {"steps": [{"delay_seconds": 0, "purpose": "Introduction"}]})
    sender = post(client, a, "/senders", {"email": "sender@example.com", "provider": "fake"})
    post(client, a, "/enrollments", {"version_id": version["id"], "contact_id": contact["id"], "sender_id": sender["id"], "research_job_id": job_id})
    schedule = client.get("/api/v1/outreach/scheduled", headers=a).json()[0]
    draft = post(client, a, f"/scheduled/{schedule['id']}/drafts")
    reviewed = approve_draft(client, a, {"draft": draft})
    assert not run(client, a) and provider.calls == 0
    approve(client, a, reviewed["plan"])
    assert run(client, a)
    outbound = get_message(client, a, reviewed)
    assert outbound["provider_message_id"] and provider.calls == 1
    # Acceptance is not delivery: no delivery webhook transport is available yet.
    assert query(client, a)["metrics"]["outreach"]["delivered"]["numerator"] == 0
    incoming = ingest(client, a, {"sender": sender}, event(outbound, body="Let's schedule a meeting."))
    assert run(client, a)
    incoming = client.get("/api/v1/inbox/messages/" + incoming["id"], headers=a).json()
    assert incoming["classification"]["category"] == "meeting_intent"
    pipeline = next(p for p in pipelines(client, a) if p["contact_id"] == contact["id"])
    start = datetime.now(timezone.utc) + timedelta(days=2)
    calendar = create(client, a, "/calendar/schedule", {"pipeline_id": pipeline["id"], "integration_id": calendar_id, "brain_version_id": brain["id"], "request_key": "journey-calendar", "inbound_message_id": incoming["id"], "classification_id": incoming["classification"]["id"], "title": "Reviewed discovery call", "attendees": ["jane@example.com"], "timezone": "UTC", "start": start.isoformat(), "end": (start + timedelta(minutes=30)).isoformat()})
    assert not run(client, a) and transport.calls == 0
    approve(client, a, calendar["plan"])
    assert run(client, a)
    assert get_action(client, a, calendar)["state"] == "confirmed"
    crm = create(client, a, "/crm/sync", {"pipeline_id": pipeline["id"], "integration_id": crm_id, "brain_version_id": brain["id"], "request_key": "journey-crm", "object_type": "contact"})
    assert not run(client, a)
    approve(client, a, crm["plan"])
    assert run(client, a)
    assert get_action(client, a, crm)["state"] == "confirmed"
    report = query(client, a)
    assert report["metrics"]["contacted_to_confirmed_meeting"]["numerator"] == 1
    assert report["recommendations"] and report["approval"]["can_execute"] is False
    # A small sample cannot justify an automatic next action. Explicit review remains required.
    next_plan = client.post(f"/api/v1/gtm/goals/{goal['id']}/plans", headers=a, json={"mode": "research_template"}).json()
    assert not run(client, a)
    next_cycle = approve(client, a, next_plan)
    assert run(client, a)
    assert client.get(f"/api/v1/gtm/cycles/{next_cycle['id']}", headers=a).json()["status"] == "completed"
    assert provider.calls == 1 and transport.calls == 2
