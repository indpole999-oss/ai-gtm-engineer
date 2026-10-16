"""Versioned, read-only projections of canonical evidence; never creates commands.

Historical dimensions come only from immutable snapshots. Mutable CRM/person fields
are deliberately not joined into historical metrics. No LLM or provider is used.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from backend.planning_service import digest
from backend.planning_models import ExecutionCycle
from backend.outreach_models import Message, MessageDraft, DeliveryEvent
from backend.inbox_models import InboundMessage, ReplyClassification
from backend.outcome_models import PipelineRecord, PipelineHistory, OutcomeAction, STAGES
from backend.research_models import ResearchJob, AccountIntelligence

VERSION = "gtm-insights-v1"
MIN_SAMPLE = 20
MAX_ROWS = 20000
LIMITATIONS = [
    "Descriptive associations only; no causal, statistical-significance or revenue prediction claims.",
    "Provider acceptance is not delivery; a scheduled meeting is not an attended meeting.",
    "Unknown dimensions are retained; mutable company/contact fields are not historical evidence.",
    "Conversions require both observed stages in order; skipped stages are not inferred.",
    "Late-arriving evidence can change a later report; retain the returned manifest and report hash.",
]


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat()


async def rows(db, model):
    # Explicit tenant predicate in addition to ORM tenancy and PostgreSQL RLS.
    wid = db.info.get("workspace_id")
    if not wid:
        raise HTTPException(403, "Workspace required")
    result = list((await db.scalars(select(model).where(model.workspace_id == wid).limit(MAX_ROWS + 1))).all())
    if len(result) > MAX_ROWS:
        raise HTTPException(422, "Analytics evidence exceeds synchronous limit; batched reporting is required. No partial metrics returned.")
    return result


def event(kind, row, occurred, *, dimensions=None, evidence=None, **extra):
    return {"id": f"{row.__tablename__}:{row.id}:{kind}", "kind": kind,
        "occurred_at": iso(occurred), "recorded_at": iso(row.created_at),
        "source": {"table": row.__tablename__, "id": str(row.id)},
        "dimensions": dimensions or {}, "evidence": evidence or {}, **extra}


def dimensions(envelope):
    # There is no typed persisted industry/persona/signal or angle taxonomy yet.
    result = {k: envelope.get(k) for k in ("company_id", "contact_id", "campaign_id", "sequence_id",
        "sequence_version_id", "sequence_step_id", "brain_version_id", "research_job_id")}
    result.update({k: None for k in ("industry", "company_size", "persona", "buying_signal", "message_angle")})
    research = envelope.get("buyer_reasoning", {})
    result["segment"] = research.get("icp_used") or None
    # Exact recipient match only; a research buyer is an unverified observation,
    # not proof that every contact at the company has that persona.
    buyers = [b for b in research.get("buyers", []) if b.get("email") and
        b["email"].casefold() == envelope.get("recipient", "").casefold() and b.get("claim_indices")]
    titles = {b.get("title") for b in buyers if b.get("title")}
    if len(titles) == 1:
        result["persona"] = next(iter(titles))
    signal = research.get("why_now", {})
    if signal.get("claim_indices") and signal.get("reasoning"):
        result["buying_signal"] = signal["reasoning"]
    # Only recognize the exact persisted template CTA, never infer one from prose.
    cta = "Would a conversation be useful?"
    result["cta"] = cta if envelope.get("composition_method") == "evidence_template" and cta in envelope.get("body", "").splitlines() else None
    return result


async def normalize(db, end):
    end = utc(end)
    sources = {}
    for model in (PipelineRecord, PipelineHistory, MessageDraft, Message, DeliveryEvent,
                  InboundMessage, ReplyClassification, OutcomeAction, ResearchJob, AccountIntelligence, ExecutionCycle):
        sources[model] = [r for r in await rows(db, model) if utc(r.created_at) < end]
    drafts = {r.id: r for r in sources[MessageDraft]}
    pipelines = {r.id: r for r in sources[PipelineRecord]}
    cycles = {r.plan_id: str(r.id) for r in sources[ExecutionCycle]}
    reports = {r.job_id: r for r in sources[AccountIntelligence]}
    events = []
    for r in sources[PipelineHistory]:
        p = pipelines.get(r.pipeline_id)
        if not p:
            continue
        events.append(event("pipeline_transition", r, r.created_at,
            dimensions={"company_id": str(p.company_id), "contact_id": str(p.contact_id) if p.contact_id else None,
                "campaign_id": str(r.campaign_id) if r.campaign_id else None,
                "sequence_version_id": str(r.sequence_version_id) if r.sequence_version_id else None},
            evidence={**r.evidence, "source_kind": r.source, "reason": r.reason}, pipeline_id=str(p.id), entity_type="contact" if p.contact_id else "account",
            from_stage=r.from_stage, stage=r.to_stage, applied=r.applied, cycle_id=str(r.cycle_id) if r.cycle_id else None))
    for r in sources[ResearchJob]:
        report = reports.get(r.id)
        if r.status == "completed" and r.completed_at and utc(r.completed_at) < end and report:
            events.append(event("research_completed", r, r.completed_at, dimensions={"company_id": str(r.company_id),
                "brain_version_id": str(r.brain_version_id), "research_job_id": str(r.id)},
                evidence={"account_intelligence_id": str(report.id), "report_hash": digest(report.result)}))
    for r in sources[Message]:
        draft = drafts.get(r.draft_id)
        if not draft or r.state != "sent" or not r.provider_message_id or not r.accepted_at or utc(r.accepted_at) >= end:
            continue
        env = draft.envelope
        events.append(event("sent", r, r.accepted_at, dimensions={**dimensions(env), "message_id": str(r.id)},
            evidence={k: env.get(k) for k in ("evidence_id", "research_claim_id", "brain_claim_id", "brain_hash", "sequence_hash", "account_intelligence_id")},
            draft_id=str(draft.id), draft_hash=draft.content_hash, cycle_id=cycles.get(r.plan_id)))
    sent = {e["source"]["id"]: e for e in events if e["kind"] == "sent"}
    for r in sources[DeliveryEvent]:
        original = sent.get(str(r.message_id))
        if original:
            events.append(event("delivery_" + r.kind, r, r.created_at, dimensions=original["dimensions"], evidence={"message_id": str(r.message_id)}))
    latest = {}
    for r in sources[ReplyClassification]:
        prior = latest.get(r.inbound_message_id)
        if prior is None or r.number > prior.number:
            latest[r.inbound_message_id] = r
    for r in sources[InboundMessage]:
        original = sent.get(str(r.outbound_message_id))
        classification = latest.get(r.id)
        if not original or r.auto_submitted != "no" or utc(r.received_at) >= end:
            continue
        # Unclassified replies are evidence, but cannot be assumed human engagement.
        category = classification.category if classification else "unclassified"
        events.append(event("reply", r, r.received_at, dimensions=original["dimensions"],
            evidence={"classification_id": str(classification.id) if classification else None,
                "classification_number": classification.number if classification else None},
            category=category, human=category not in {"out_of_office", "unclassified"},
            positive=category in {"positive", "meeting_intent"}))
    for r in sources[OutcomeAction]:
        if r.state == "confirmed" and r.confirmed_at and utc(r.confirmed_at) < end and r.external_id and r.receipt and r.receipt.get("status") == "confirmed":
            events.append(event("meeting_scheduled" if r.kind == "calendar_schedule" else "crm_synced", r, r.confirmed_at,
                pipeline_id=str(r.pipeline_id), evidence={"receipt_hash": digest(r.receipt), "payload_hash": r.content_hash},
                cycle_id=cycles.get(r.plan_id)))
    return sorted(events, key=lambda e: (e["occurred_at"], e["id"]))


def metric(numerator, denominator, numerator_ids=(), denominator_ids=()):
    return {"numerator": numerator, "denominator": denominator, "sample_size": denominator,
        "rate": numerator / denominator if denominator else None,
        "status": "available" if denominator >= MIN_SAMPLE else "insufficient_data",
        "numerator_ids": sorted(numerator_ids), "denominator_ids": sorted(denominator_ids)}


def build(events, start, end, entity_type="contact", workspace_id=None):
    start, end = iso(start), iso(end)
    # Stable source identities deduplicate replayed ingestion/projection input.
    events = sorted({e["id"]: e for e in events if e["occurred_at"] < end and e["recorded_at"] < end}.values(), key=lambda e: (e["occurred_at"], e["id"]))
    window = [e for e in events if start <= e["occurred_at"] < end]
    history = [e for e in events if e["kind"] == "pipeline_transition" and e["entity_type"] == entity_type and e["applied"]]
    by_pipeline = defaultdict(list)
    for e in history:
        by_pipeline[e["pipeline_id"]].append(e)
    cohort = {pid: es for pid, es in by_pipeline.items() if any(e["stage"] == "discovered" and start <= e["occurred_at"] < end for e in es)}
    observed = {stage: {pid for pid, es in cohort.items() if any(e["stage"] == stage for e in es)} for stage in STAGES}
    conversions = {}
    for left, right in zip(STAGES[:7], STAGES[1:8]):
        eligible = observed[left]
        converted = {pid for pid in eligible if any(b["stage"] == right and a["stage"] == left and b["occurred_at"] >= a["occurred_at"] for a in cohort[pid] for b in cohort[pid])}
        conversions[left + "_to_" + right] = metric(len(converted), len(eligible), converted, eligible)
    # Won and lost are branches, never a won -> lost conversion.
    for terminal in ("won", "lost"):
        eligible = observed["opportunity"]
        converted = {pid for pid in eligible if any(b["stage"] == terminal and a["stage"] == "opportunity" and b["occurred_at"] >= a["occurred_at"] for a in cohort[pid] for b in cohort[pid])}
        conversions["opportunity_to_" + terminal] = metric(len(converted), len(eligible), converted, eligible)
    ambiguous = {pid for pid, es in cohort.items() if len({e["stage"] for e in es if e["occurred_at"] == es[-1]["occurred_at"]}) > 1}
    current = Counter(es[-1]["stage"] for pid, es in cohort.items() if pid not in ambiguous)
    sent = {e["source"]["id"]: e for e in window if e["kind"] == "sent"}
    replies = defaultdict(list)
    deliveries = defaultdict(set)
    for e in window:
        mid = e["dimensions"].get("message_id")
        if mid not in sent or e["occurred_at"] < sent[mid]["occurred_at"]:
            continue
        if e["kind"] == "reply":
            replies[mid].append(e)
        elif e["kind"].startswith("delivery_"):
            deliveries[mid].add(e["kind"][9:])

    def performance(ids):
        ids = set(ids)
        human = {mid for mid in ids if any(e["human"] for e in replies[mid])}
        positive = {mid for mid in ids if any(e["positive"] for e in replies[mid])}
        unclassified = {mid for mid in ids if any(e["category"] == "unclassified" for e in replies[mid])}
        delivered = {mid for mid in ids if "delivered" in deliveries[mid]}
        bounced = {mid for mid in ids if "bounced" in deliveries[mid]}
        covered = {mid for mid in ids if sent[mid]["evidence"].get("evidence_id")}
        result = {"sent": len(ids), "reply": metric(len(human), len(ids), human, ids),
            "positive_reply": metric(len(positive), len(ids), positive, ids),
            "delivered": metric(len(delivered), len(ids), delivered, ids),
            "bounced": metric(len(bounced), len(ids), bounced, ids),
            "research_evidence_coverage": metric(len(covered), len(ids), covered, ids)}
        result["unclassified_reply_message_ids"] = sorted(unclassified)
        if unclassified:
            for name in ("reply", "positive_reply"):
                result[name].update(status="insufficient_data", reason="Unclassified replies prevent a complete engagement assessment")
        return result

    breakdowns = {}
    for dimension in ("industry", "company_size", "segment", "persona", "buying_signal", "campaign_id", "sequence_version_id", "message_id", "message_angle", "cta"):
        groups = defaultdict(list)
        for mid, e in sent.items():
            groups[e["dimensions"].get(dimension) or "unknown"].append(mid)
        breakdowns[dimension] = {"status": "available" if any(k != "unknown" for k in groups) else "insufficient_data",
            "cohort": "provider-confirmed messages accepted in [start,end); outcomes observed before end",
            "groups": [{"value": k, **performance(v)} for k, v in sorted(groups.items())]}
    pipeline_ids = set(cohort)
    synced = {e["pipeline_id"] for e in events if e["kind"] == "crm_synced"} & pipeline_ids
    contacted = observed["contacted"]
    contact_times = {pid: min(h["occurred_at"] for h in cohort[pid] if h["stage"] == "contacted") for pid in contacted}
    meetings = {e["pipeline_id"] for e in events if e["kind"] == "meeting_scheduled" and
        e["pipeline_id"] in contact_times and contact_times[e["pipeline_id"]] <= e["occurred_at"]}
    company_ids = {e["dimensions"].get("company_id") for es in cohort.values() for e in es}
    researched = {e["dimensions"]["company_id"] for e in events if e["kind"] == "research_completed"} & company_ids
    metrics = {"outreach": performance(sent), "contacted_to_confirmed_meeting": metric(len(meetings), len(contacted), meetings, contacted),
        "crm_confirmed_sync_coverage": metric(len(synced), len(pipeline_ids), synced, pipeline_ids),
        "account_research_coverage": metric(len(researched), len(company_ids), researched, company_ids)}
    unsupported = {"status": "insufficient_data", "value": None, "reason": "No canonical actual-cost/currency or booked-revenue ledger; budgets and won stages are not money."}
    report = {"version": VERSION, "workspace_id": str(workspace_id) if workspace_id else None, "date_range": {"start": start, "end_exclusive": end, "timezone": "UTC"},
        "minimum_recommendation_sample": MIN_SAMPLE, "entity_type": entity_type,
        "funnel": {"cohort": "Distinct pipelines discovered in [start,end); outcomes through end, no stage inference",
            "sample_size": len(cohort), "observed_stage_entries": {s: len(observed[s]) for s in STAGES},
            "current_stage_as_of_end": {s: current[s] for s in STAGES}, "ambiguous_current_stage_ids": sorted(ambiguous), "conversions": conversions},
        "event_counts": dict(sorted(Counter(e["kind"] for e in window).items())),
        "metrics": metrics, "breakdowns": breakdowns,
        "cost_per_reply": unsupported, "cost_per_meeting": unsupported, "revenue": unsupported,
        "limitations": LIMITATIONS + ["Small or recent cohorts may not have had time to respond; compare equal follow-up windows.",
            "CRM coverage means at least one confirmed sync, not present-day CRM freshness.",
            "Persona is an exact email-matched research title observation, not independent identity verification. Segment is the pinned Brain ICP, not proven segment membership.",
            "Buying signal groups exact evidence-linked research why-now statements, not verified intent or a standardized taxonomy. Missing evidence stays unknown.",
            "Industry, company-size and message-angle taxonomies are absent in canonical snapshots and remain unknown.",
            "Equal-time conflicting stage corrections have ambiguous order and are excluded from current-stage totals.",
            "Stage-entry counts are historical; current-stage counts reflect later applied corrections."],
        "approval": {"advisory_only": True, "can_execute": False, "required": "Any action requires a separately reviewed Phase 5 plan and approval."},
        "evidence_manifest": events}
    recommendations = []
    checks = [("research_coverage", metrics["account_research_coverage"], 1.0, "Review missing account research before planning outreach."),
        ("crm_coverage", metrics["crm_confirmed_sync_coverage"], 1.0, "Review unsynced pipeline records and prepare a separate CRM plan."),
        ("reply_coverage", metrics["outreach"]["reply"], 0.1, "Review message and targeting evidence; consider a separately approved, controlled comparison.")]
    for rule, m, threshold, action in checks:
        eligible = m["status"] == "available"
        gap = eligible and m["rate"] < threshold
        recommendations.append({"rule": rule, "rule_version": VERSION,
            "status": "observed_gap" if gap else "no_gap_observed" if eligible else "insufficient_data",
            "observed_gap": f"Observed rate below configured review threshold {threshold}; this is not an industry benchmark." if gap else None,
            "supporting_metric": m, "sample_size": m["sample_size"], "date_range": report["date_range"], "as_of": end,
            "threshold": threshold, "confidence": "descriptive_only" if eligible else "insufficient_data",
            "proposed_action": action if gap else "Collect more persisted evidence." if not eligible else None,
            "expected_outcome": "Better evidence for a human decision; no guaranteed conversion or revenue uplift.",
            "cost": {"status": "unavailable", "value": None}, "risk": "Selection bias, incomplete follow-up and uncertain source assertions.",
            "required_approval": True, "can_execute": False, "limitations": report["limitations"]})
    report["recommendations"] = recommendations
    report["evidence_hash"] = digest(events)
    report["report_hash"] = digest(report)
    return report


async def report(db, start, end, entity_type):
    now = datetime.now(timezone.utc)
    if start.tzinfo is None or end.tzinfo is None or utc(start) >= utc(end) or utc(end) > now:
        raise HTTPException(422, "Use offset-aware start < end <= now; interval is start-inclusive/end-exclusive")
    result = build(await normalize(db, end), start, end, entity_type, db.info.get("workspace_id"))
    result["generated_at"] = iso(now)
    return result
