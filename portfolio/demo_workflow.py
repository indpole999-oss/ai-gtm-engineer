"""Reproducible GTM workflow reference: test fixtures only, standard library only.

No network calls, external emails, CRM writes, or API keys. All companies are fictional.
Run: python portfolio/demo_workflow.py aster
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from typing import Any

FIXTURES: dict[str, dict[str, Any]] = {
    "aster": {
        "name": "Aster Cloud",
        "industry": "SaaS",
        "employees": 220,
        "signal": "Hiring revenue operations engineers",
        "evidence": [
            {"fact": "B2B subscription software", "source": "fictional-fixture:sector"},
            {"fact": "Hiring revenue operations engineers", "source": "fictional-fixture:signal"},
        ],
        "contact": "team@aster.example",
    },
    "ridge": {
        "name": "Ridgeway Logistics",
        "industry": "Transport",
        "employees": 820,
        "signal": None,
        "evidence": [
            {"fact": "Freight logistics operator", "source": "fictional-fixture:sector"}
        ],
        "contact": None,
    },
    "mira": {
        "name": "MiraCare Analytics",
        "industry": "Healthtech",
        "employees": 110,
        "signal": "Expanded its data partnerships team",
        "evidence": [
            {"fact": "Health analytics platform", "source": "fictional-fixture:sector"},
            {"fact": "Expanded its data partnerships team", "source": "fictional-fixture:signal"},
        ],
        "contact": "team@miracare.example",
    },
}


def research_account(key: str) -> dict[str, Any]:
    """Return source-tagged synthetic data; reject nonexistent accounts."""
    if key not in FIXTURES:
        raise ValueError("Unknown fictional fixture")
    account = deepcopy(FIXTURES[key])
    for piece in account["evidence"]:
        if not piece["fact"] or not piece["source"]:
            raise ValueError("Evidence missing fact/source")
    return account


def enrich_mock(account: dict[str, Any]) -> dict[str, Any]:
    """Simulate a provider waterfall without making any provider calls."""
    contact = account["contact"]
    return {
        "provider": "fictional-fixture",
        "attempts": ["mock-provider-primary", "mock-provider-fallback"] if not contact else ["mock-provider-primary"],
        "contact": contact,
        "verified_real_world": False,
    }


def qualify(account: dict[str, Any]) -> dict[str, Any]:
    """Explainable 100-point ICP rubric, with no LLM judgment."""
    checks = {
        "industry": account["industry"] in {"SaaS", "Healthtech"},
        "employee_range": 50 <= account["employees"] <= 500,
        "buying_signal": bool(account["signal"]),
        "evidence_completeness": len(account["evidence"]) >= 2,
    }
    weights = {"industry": 40, "employee_range": 20, "buying_signal": 25, "evidence_completeness": 15}
    score = sum(weights[name] for name, passes in checks.items() if passes)
    return {"checks": checks, "weights": weights, "score": score, "tier": "HIGH FIT" if score >= 80 else ("REVIEW" if score >= 50 else "LOW FIT")}


def create_draft(account: dict[str, Any]) -> dict[str, Any]:
    """Prepare a draft using only supplied evidence. Never send."""
    signal = account["signal"]
    line = f"The sample data mentions {signal.lower()}." if signal else "The sample data does not contain a verified buying signal."
    return {
        "subject": f"Idea for {account['name']}",
        "body": f"Hi there,\n\n{line} I'm exploring ways that a structured account-intelligence and revenue-automation workflow could support teams like yours.\n\nWould a short conversation be useful?\n\n— Anil\n\n[FICTIONAL SAMPLE ONLY — NOT FOR SENDING]",
        "approval_state": "PENDING_REVIEW",
        "sent": False,
    }


def run_workflow(key: str) -> dict[str, Any]:
    """Research -> mock enrichment -> scoring -> human-approval-gated draft."""
    account = research_account(key)
    enrichment = enrich_mock(account)
    quality = qualify(account)
    draft = create_draft(account)
    return {
        "mode": "OFFLINE_FIXTURE_ONLY",
        "account": account["name"],
        "evidence": account["evidence"],
        "enrichment": enrichment,
        "qualification": quality,
        "draft": draft,
        "external_network_calls": 0,
        "emails_sent": 0,
        "crm_writes": 0,
        "calendar_events_created": 0,
    }


def approve_sample(result: dict[str, Any], reviewer: str) -> dict[str, Any]:
    """Demonstrate approval state change; deliberately does not execute any side effect."""
    if not reviewer.strip():
        raise ValueError("Reviewer is required")
    result = deepcopy(result)
    if result["mode"] != "OFFLINE_FIXTURE_ONLY":
        raise ValueError("Only fictional fixture results may be approved")
    result["draft"]["approval_state"] = "APPROVED_IN_MEMORY_ONLY"
    result["draft"]["reviewed_by"] = reviewer
    return result


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "aster"
    print(json.dumps(run_workflow(key), indent=2, ensure_ascii=False))
