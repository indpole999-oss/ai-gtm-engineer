"""Phase 9: persisted evidence, reproducible cohorts and a read-only boundary."""
from datetime import datetime, timezone, timedelta
from uuid import UUID
import pytest
from sqlalchemy import select, func
from backend import execution_worker as worker
from backend.database import AsyncSessionLocal, engine, WorkspaceMembership
from backend.planning_models import ActionCommand, DomainEvent, PlanVersion
from backend.insights_service import build, dimensions, MIN_SAMPLE
from test_workspace_security import signup, company
from test_research import fake_research  # noqa: F401
from test_outreach import provider, ready, setup_outreach, expire  # noqa: F401
from test_inbox import sent, ingest, event
from test_outcomes import transport, crm_ready, create, run, retry, calendar_ready  # noqa: F401
from test_planning_execution import approve

BASE = "/api/v1/insights"
START = datetime(2020, 1, 1, tzinfo=timezone.utc)


def query(client, headers, end=None, **params):
    result = client.get(BASE, headers=headers, params={"start": START.isoformat(),
        "end": (end or datetime.now(timezone.utc)).isoformat(), **params})
    assert result.status_code == 200, result.text
    return result.json()


def test_empty_unknowns_and_no_execution_surface(client):
    a = signup(client, "empty-insights@example.com")
    report = query(client, a)
    assert report["funnel"]["sample_size"] == 0
    assert report["metrics"]["outreach"]["reply"]["rate"] is None
    assert all(r["status"] == "insufficient_data" for r in report["recommendations"])
    assert report["cost_per_meeting"]["value"] is None and report["revenue"]["value"] is None
    assert report["approval"]["can_execute"] is False
    for path in (BASE, BASE + "/execute", BASE + "/recommendations/execute"):
        assert client.post(path, headers=a, json={"approved": True}).status_code in (404, 405)


@pytest.mark.parametrize("role", ["owner", "admin", "member", "viewer"])
def test_roles_isolation_and_no_mutations(client, role):
    a, b = signup(client, "a-insights@example.com"), signup(client, "b-insights@example.com")
    company(client, a)
    company(client, b)
    async def change():
        async with AsyncSessionLocal() as db:
            m = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            m.role = role
            await db.commit()
    client.portal.call(change)
    result = query(client, a, entity_type="account")
    other = query(client, b, entity_type="account")
    assert result["funnel"]["sample_size"] == other["funnel"]["sample_size"] == 1
    assert {e["id"] for e in result["evidence_manifest"]}.isdisjoint(e["id"] for e in other["evidence_manifest"])
    assert client.get(BASE, headers={**a, "X-Workspace-ID": b["X-Workspace-ID"]}, params={"start":START.isoformat(), "end":datetime.now(timezone.utc).isoformat()}).status_code == 403
    assert client.get(BASE).status_code == 401


@pytest.mark.parametrize("start,end", [("2026-01-01", "2026-02-01"), ("2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z"), ("2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")])
def test_invalid_ranges(client, start, end):
    a = signup(client, "dates-insights@example.com")
    assert client.get(BASE, headers=a, params={"start":start,"end":end}).status_code == 422


def test_send_confirmations_replies_overrides_and_restart(client, fake_research, provider):
    a, data, outbound = sent(client, fake_research, provider)
    incoming = ingest(client, a, data, event(outbound))
    ingest(client, a, data, event(outbound))
    run(client, a)
    end = datetime.now(timezone.utc)
    before = query(client, a, end)
    assert before["metrics"]["outreach"]["sent"] == 1
    assert before["metrics"]["outreach"]["reply"]["numerator"] == 1
    assert before["metrics"]["outreach"]["positive_reply"]["numerator"] == 1
    assert before["metrics"]["outreach"]["delivered"]["numerator"] == 0
    assert before["breakdowns"]["persona"]["groups"][0]["value"] == "VP Revenue"
    assert before["breakdowns"]["sequence_version_id"]["groups"][0]["value"] == data["version"]["id"]
    assert before["breakdowns"]["industry"]["status"] == "insufficient_data"
    assert before["event_counts"].get("meeting_scheduled", 0) == 0
    r = client.post("/api/v1/inbox/messages/" + incoming["id"] + "/override", headers=a,
        json={"category":"out_of_office","reason":"Reviewed automatic absence response","expected_number":1,"reviewed":True})
    assert r.status_code == 201, r.text
    after = query(client, a)
    assert after["metrics"]["outreach"]["reply"]["numerator"] == 0
    # Historical persona/recipient dimensions must not follow mutable contacts.
    contact_id = data["draft"]["envelope"]["contact_id"]
    assert client.patch("/api/v1/contacts/" + contact_id, headers=a, json={"title":"Changed executive title"}).status_code == 200
    client.portal.call(engine.dispose)
    assert query(client, a, end)["report_hash"] == before["report_hash"]
    assert provider.calls == 1


def test_drafts_failures_and_reads_cannot_count_or_send(client, fake_research, provider):
    a, data, reviewed, cycle = ready(client, fake_research)
    assert query(client, a)["metrics"]["outreach"]["sent"] == 0
    assert provider.calls == 0
    provider.mode = "failure"
    run(client, a)
    assert query(client, a)["metrics"]["outreach"]["sent"] == 0
    assert provider.calls == 1
    async def counts():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            return [await db.scalar(select(func.count()).select_from(m)) for m in (ActionCommand, DomainEvent, PlanVersion)]
    before = client.portal.call(counts)
    query(client, a)
    assert client.portal.call(counts) == before and provider.calls == 1


def test_crm_confirmation_reconciliation_not_attempt_count(client, transport):
    a, body = crm_ready(client, transport)
    action = create(client, a, "/crm/sync", body)
    approve(client, a, action["plan"])
    transport.mode = "lost_ack"
    run(client, a)
    assert query(client, a, entity_type="account")["metrics"]["crm_confirmed_sync_coverage"]["numerator"] == 0
    transport.mode = "success"
    retry(client, a, action)
    run(client, a)
    result = query(client, a, entity_type="account")
    assert result["event_counts"]["crm_synced"] == 1
    assert result["metrics"]["crm_confirmed_sync_coverage"]["numerator"] == 1
    assert transport.calls == 1


def test_calendar_only_confirmed_and_pipeline_corrections(client, fake_research, provider, transport):
    a, body = calendar_ready(client, fake_research, provider, transport)
    action = create(client, a, "/calendar/schedule", body)
    assert query(client, a)["metrics"]["contacted_to_confirmed_meeting"]["numerator"] == 0
    approve(client, a, action["plan"])
    transport.mode = "failure"
    run(client, a)
    assert query(client, a)["event_counts"].get("meeting_scheduled", 0) == 0
    retry(client, a, action)
    transport.mode = "success"
    run(client, a)
    result = query(client, a)
    assert result["metrics"]["contacted_to_confirmed_meeting"]["numerator"] == 1
    path = "/api/v1/outcomes/pipeline/" + body["pipeline_id"]
    for stage in ("opportunity", "won", "lost"):
        p = client.get(path, headers=a).json()
        r = client.post(path + "/stage", headers=a, json={"stage":stage,"expected_revision":p["revision"],
            "reason":"Reviewed business outcome correction","evidence_kind":"explicit_user","reviewed":True})
        assert r.status_code == 200, r.text
    result = query(client, a)
    assert result["funnel"]["current_stage_as_of_end"]["lost"] == 1
    assert result["funnel"]["current_stage_as_of_end"]["won"] == 0
    assert result["funnel"]["observed_stage_entries"]["won"] == 1
    assert result["revenue"]["value"] is None


def synthetic(kind, day, key, **extra):
    timestamp = datetime(2025, 1, day, tzinfo=timezone.utc).isoformat()
    return {"id": key, "kind":kind, "source":{"id":key,"table":"test"}, "occurred_at":timestamp,
        "recorded_at":timestamp,"dimensions":{},"evidence":{}, **extra}


def hist(day, key, stage, **extra):
    return synthetic("pipeline_transition", day, key, pipeline_id="p", entity_type="contact", applied=True, stage=stage, **extra)


def test_cohort_corrections_duplicates_and_terminal_branches():
    events = [hist(1,"a","discovered"),hist(2,"b","contacted"),hist(3,"c","opportunity"),hist(4,"d","won"),hist(5,"e","lost")]
    report = build(events + events, START, datetime(2025,2,1,tzinfo=timezone.utc))
    assert report["funnel"]["sample_size"] == 1
    assert report["funnel"]["current_stage_as_of_end"]["won"] == 0
    assert report["funnel"]["current_stage_as_of_end"]["lost"] == 1
    assert report["funnel"]["observed_stage_entries"]["won"] == 1
    assert report["funnel"]["observed_stage_entries"]["qualified"] == 0
    assert report["funnel"]["conversions"]["qualified_to_contacted"]["rate"] is None
    assert "won_to_lost" not in report["funnel"]["conversions"]
    assert report["funnel"]["conversions"]["opportunity_to_won"]["rate"] == 1
    assert report["revenue"]["value"] is None


def test_timezone_half_open_range_and_no_reversed_conversion():
    events = [hist(1,"a","discovered"), hist(2,"b","engaged"), hist(3,"c","contacted")]
    a = build(events, START, datetime.fromisoformat("2025-01-03T05:30:00+05:30"))
    b = build(events, START, datetime.fromisoformat("2025-01-03T00:00:00+00:00"))
    assert a["report_hash"] == b["report_hash"]
    assert a["funnel"]["observed_stage_entries"]["contacted"] == 0
    c = build(events, START, datetime(2025,2,1,tzinfo=timezone.utc))
    assert c["funnel"]["conversions"]["contacted_to_engaged"]["rate"] == 0


def test_minimum_sample_rules_evidence_and_noncausal_recommendations():
    events = [synthetic("sent",1,str(i), dimensions={"message_id":str(i),"campaign_id":"campaign"}) for i in range(MIN_SAMPLE)]
    report = build(events, START, datetime(2025,2,1,tzinfo=timezone.utc))
    recommendation = next(r for r in report["recommendations"] if r["rule"] == "reply_coverage")
    assert recommendation["status"] == "observed_gap"
    assert recommendation["supporting_metric"]["denominator"] == MIN_SAMPLE
    assert len(recommendation["supporting_metric"]["denominator_ids"]) == MIN_SAMPLE
    assert recommendation["required_approval"] and not recommendation["can_execute"]
    assert recommendation["confidence"] == "descriptive_only" and recommendation["cost"]["value"] is None
    small = build(events[:-1], START, datetime(2025,2,1,tzinfo=timezone.utc))
    assert small["recommendations"][-1]["status"] == "insufficient_data"


def test_no_invented_dimensions_or_cta():
    d = dimensions({"body":"Maybe ask for a demo", "recipient":"other@example.com", "buyer_reasoning":{
        "buyers":[{"email":"buyer@example.com","title":"CEO","claim_indices":[0]}]}})
    assert all(d[k] is None for k in ("industry","company_size","persona","buying_signal","message_angle","cta"))


def test_signal_only_with_evidence_and_ambiguous_persona():
    envelope = {"recipient":"buyer@example.com","buyer_reasoning":{
        "buyers":[{"email":"buyer@example.com","title":t,"claim_indices":[0]} for t in ("CEO","CFO")],
        "why_now":{"reasoning":"Dated expansion announcement","claim_indices":[0]}}}
    assert dimensions(envelope)["persona"] is None
    assert dimensions(envelope)["buying_signal"] == "Dated expansion announcement"
    envelope["buyer_reasoning"]["why_now"]["claim_indices"] = []
    assert dimensions(envelope)["buying_signal"] is None


def test_late_recording_and_ambiguous_stage_order_do_not_invent_state():
    late = hist(2,"late","won")
    late["recorded_at"] = datetime(2025,3,1,tzinfo=timezone.utc).isoformat()
    events = [hist(1,"a","discovered"),hist(2,"b","won"),hist(2,"c","lost"),late]
    result = build(events, START, datetime(2025,2,1,tzinfo=timezone.utc))
    assert result["funnel"]["ambiguous_current_stage_ids"] == ["p"]
    assert result["funnel"]["current_stage_as_of_end"]["won"] == 0
    assert len(result["evidence_manifest"]) == 3


def test_large_evidence_fails_closed_without_partial_metrics(client, monkeypatch):
    import backend.insights_service as service
    a = signup(client, "limit-insights@example.com")
    company(client,a,domain="one.example")
    company(client,a,domain="two.example")
    monkeypatch.setattr(service,"MAX_ROWS",1)
    result = client.get(BASE,headers=a,params={"start":START.isoformat(),"end":datetime.now(timezone.utc).isoformat()})
    assert result.status_code == 422 and "No partial metrics" in result.text


def test_pending_classification_cannot_trigger_low_reply_recommendation():
    events = [synthetic("sent",1,str(i),dimensions={"message_id":str(i)}) for i in range(MIN_SAMPLE)]
    events.append(synthetic("reply",2,"pending",dimensions={"message_id":"0"},category="unclassified",human=False,positive=False))
    result = build(events,START,datetime(2025,2,1,tzinfo=timezone.utc))
    assert result["metrics"]["outreach"]["reply"]["status"] == "insufficient_data"
    assert result["recommendations"][-1]["status"] == "insufficient_data"
