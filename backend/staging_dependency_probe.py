"""Opt-in, read-only staging source probe. No model or execution records."""
import asyncio
import json
import logging
import os
from uuid import UUID

from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.planning_models import PlanVersion
from backend.planning_service import digest
from backend.retrieval import retrieve, retrieval_trace, RetrievalError

logger = logging.getLogger(__name__)


def probe_enabled():
    return (os.environ.get("RENDER_SERVICE_ID") == "srv-daui93navr4c739a4chg"
            and os.environ.get("GTM_HOSTED_AI_ENABLED", "false").lower() == "false"
            and bool(os.environ.get("GTM_SOURCE_PROBE_PLAN")))


def capture(url):
    events = []
    token = retrieval_trace.set(events)
    try:
        source = retrieve(url)
        return {"status": "PASS", "http_trace": events, "title": source["title"],
                "characters": len(source["content"]), "sha256": source["content_hash"],
                "excerpt": source["content"][:200], "extractor": source["extractor_version"]}
    except RetrievalError as error:
        return {"status": "BLOCKED", "http_trace": events, "reason": str(error)}
    finally:
        retrieval_trace.reset(token)


async def run():
    if not probe_enabled():
        return
    try:
        workspace_id = UUID(os.environ["GTM_SOURCE_PROBE_WORKSPACE"])
        plan_id = UUID(os.environ["GTM_SOURCE_PROBE_PLAN"])
        expected_hash = os.environ["GTM_SOURCE_PROBE_HASH"]
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=workspace_id, workspace_role="viewer")
            plan = await db.scalar(select(PlanVersion).where(PlanVersion.id == plan_id))
            if not plan or plan.content_hash != expected_hash or digest(plan.document) != expected_hash:
                raise ValueError("Pinned plan hash mismatch")
            urls = list(dict.fromkeys(url for target in plan.document["targets"] for url in target["source_urls"]))
        if not 1 <= len(urls) <= 3:
            raise ValueError("Probe requires one to three pinned sources")
        for url in urls:
            result = await asyncio.to_thread(capture, url)
            logger.info("staging_source_probe " + json.dumps({"plan_id": str(plan_id),
                "plan_hash": expected_hash, "url": url, "model_called": False, **result}))
    except Exception as error:
        # Do not expose database connection strings or arbitrary provider errors.
        logger.error("staging_source_probe_failed", extra={"error_type": type(error).__name__})
