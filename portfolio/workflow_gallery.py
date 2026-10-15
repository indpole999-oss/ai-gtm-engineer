"""Eight safe GTM workflow reference implementations, using fictional fixture data.

These are training/portfolio examples, not live provider integrations.
No HTTP, SMTP, CRM credentials, calendar calls, or paid AI dependencies.
Usage: python portfolio/workflow_gallery.py all
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from demo_workflow import research_account, enrich_mock, qualify, create_draft
except ImportError:
    from portfolio.demo_workflow import research_account, enrich_mock, qualify, create_draft


@dataclass
class SafeWorkspace:
    """Temporary in-memory stores for a fictional demo workspace."""
    account_key: str = "aster"
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    activity_log: list[dict[str, Any]] = field(default_factory=list)
    external_calls: int = 0

    def log(self, stage: str, detail: str) -> None:
        self.activity_log.append({"stage": stage, "detail": detail})


def account_research(ctx: SafeWorkspace) -> dict[str, Any]:
    account = research_account(ctx.account_key)
    ctx.log("research", f"loaded {len(account['evidence'])} fictional source-tagged facts")
    return {
        "workflow": "01_account_research",
        "account": account["name"],
        "facts": deepcopy(account["evidence"]),
        "fictional": True,
    }


def prospect_enrichment(ctx: SafeWorkspace) -> dict[str, Any]:
    account = research_account(ctx.account_key)
    data = enrich_mock(account)
    ctx.log("enrichment", "mock waterfall executed (no providers contacted)")
    return {
        "workflow": "02_prospect_enrichment",
        "provider": data["provider"],
        "attempted_mock_providers": data["attempts"],
        "contact": data["contact"],
        "real_world_verified": False,
    }


def icp_qualification(ctx: SafeWorkspace) -> dict[str, Any]:
    data = qualify(research_account(ctx.account_key))
    ctx.log("qualification", f"score={data['score']}; tier={data['tier']}")
    return {"workflow": "03_icp_qualification", **data}


def outreach_drafting(ctx: SafeWorkspace) -> dict[str, Any]:
    data = create_draft(research_account(ctx.account_key))
    ctx.log("outreach", "draft created; not sent; human approval pending")
    return {"workflow": "04_outreach_drafting", **data}


def crm_sync(ctx: SafeWorkspace) -> dict[str, Any]:
    """Idempotent fictional local-only CRM write, never calls a provider."""
    account = research_account(ctx.account_key)
    result = qualify(account)
    record_id = f"fictional-crm:{ctx.account_key}"
    ctx.records[record_id] = {
        "record_id": record_id,
        "account_name": account["name"],
        "qualification": result["tier"],
        "status": "TEST_ONLY_NOT_SYNCED_EXTERNALLY",
    }
    ctx.log("crm", f"upserted in-memory record {record_id}")
    return {"workflow": "05_crm_sync_mock", "record": deepcopy(ctx.records[record_id]), "external_write": False}


def calendar_scheduling(ctx: SafeWorkspace) -> dict[str, Any]:
    """Creates a preview in a deterministic UTC timeslot, never a real meeting."""
    anchor = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
    end = anchor + timedelta(minutes=30)
    preview = {
        "id": f"fictional-calendar:{ctx.account_key}",
        "title": f"Sample review: {research_account(ctx.account_key)['name']}",
        "start_utc": anchor.isoformat(),
        "end_utc": end.isoformat(),
        "status": "PREVIEW_ONLY_PENDING_APPROVAL",
        "external_event_created": False,
    }
    ctx.log("calendar", "generated UTC preview without booking")
    return {"workflow": "06_calendar_scheduling_mock", "event": preview}


def gtm_reporting(ctx: SafeWorkspace) -> dict[str, Any]:
    """Report only recorded local activity; do not fabricate revenue metrics."""
    count: dict[str, int] = {}
    for activity in ctx.activity_log:
        count[activity["stage"]] = count.get(activity["stage"], 0) + 1
    return {
        "workflow": "07_gtm_reporting_mock",
        "events_recorded": len(ctx.activity_log),
        "stage_counts": count,
        "revenue_attributed": None,
        "claim": "Test-event counts only; no verified commercial outcome",
    }


def agent_orchestration(ctx: SafeWorkspace) -> dict[str, Any]:
    """Coordinates the first six steps without external actions."""
    sequence = [
        account_research, prospect_enrichment, icp_qualification,
        outreach_drafting, crm_sync, calendar_scheduling,
    ]
    steps = []
    for work in sequence:
        result = work(ctx)
        steps.append({"name": result["workflow"], "status": "COMPLETE_LOCAL_SAMPLE"})
    report = gtm_reporting(ctx)
    ctx.log("orchestration", "six steps run with no external side effects")
    return {
        "workflow": "08_agent_orchestration_mock",
        "steps": steps,
        "report": report,
        "pending_human_approval": True,
        "emails_sent": 0,
        "crm_external_writes": 0,
        "calendar_external_writes": 0,
        "external_calls": ctx.external_calls,
    }


WORKFLOWS = {
    "research": account_research,
    "enrichment": prospect_enrichment,
    "qualification": icp_qualification,
    "outreach": outreach_drafting,
    "crm": crm_sync,
    "calendar": calendar_scheduling,
    "reporting": gtm_reporting,
    "orchestration": agent_orchestration,
}


def run(name: str, account: str = "aster") -> dict[str, Any]:
    ctx = SafeWorkspace(account_key=account)
    if name == "all":
        output = agent_orchestration(ctx)
        return {
            "mode": "OFFLINE_FICTIONAL_FIXTURE",
            "account_fixture": account,
            "orchestration": output,
            "activity_log": deepcopy(ctx.activity_log),
        }
    if name not in WORKFLOWS:
        raise ValueError(f"Unknown workflow {name!r}; valid: {', '.join(WORKFLOWS)}")
    return {
        "mode": "OFFLINE_FICTIONAL_FIXTURE",
        "account_fixture": account,
        "result": WORKFLOWS[name](ctx),
        "external_calls": ctx.external_calls,
    }


if __name__ == "__main__":
    workflow = sys.argv[1] if len(sys.argv) > 1 else "all"
    fixture = sys.argv[2] if len(sys.argv) > 2 else "aster"
    print(json.dumps(run(workflow, fixture), indent=2, ensure_ascii=False))
