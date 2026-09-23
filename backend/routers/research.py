from datetime import datetime
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import select
from backend.database import Company
from backend.brain_models import CompanyBrainVersion
from backend.research_models import ResearchJob, SourceFetch, EvidenceItem, ResearchClaim, AccountIntelligence, ClaimVerification
from backend.research_service import scoped_record
from backend.tenancy import get_current_workspace, get_workspace_db

router = APIRouter()


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewed_text: str = Field(min_length=1, max_length=3000)
    decision: Literal["verified", "rejected"]
    reason: str = Field(min_length=20, max_length=3000)


@router.post("/claims/{claim_id}/verification", status_code=201)
async def verify_claim(claim_id: UUID, body: VerificationRequest, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    claim = await scoped_record(db, ResearchClaim, claim_id)
    if body.reviewed_text != claim.text:
        raise HTTPException(409, "Review the exact claim text")
    if body.decision == "verified" and not claim.evidence_id:
        raise HTTPException(422, "Evidence is required to verify a factual claim")
    row = ClaimVerification(claim_id=claim.id, user_id=ctx.user_id, decision=body.decision, reason=body.reason)
    db.add(row)
    await db.commit()
    return {"id": row.id, "decision": row.decision, "method": "workspace_admin_review"}


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: UUID
    brain_version_id: UUID
    source_urls: list[HttpUrl] = Field(min_length=1, max_length=3)


@router.post("/jobs", status_code=201)
async def create_job(body: ResearchRequest, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    await scoped_record(db, Company, body.company_id)
    brain = await scoped_record(db, CompanyBrainVersion, body.brain_version_id)
    if brain.status != "published":
        raise HTTPException(409, "Publish Company Brain before researching")
    row = ResearchJob(company_id=body.company_id, brain_version_id=body.brain_version_id,
                      source_urls=[str(url) for url in body.source_urls], created_by=ctx.user_id)
    db.add(row)
    await db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/jobs")
async def list_jobs(company_id: UUID | None = None, db=Depends(get_workspace_db)):
    query = select(ResearchJob).order_by(ResearchJob.created_at.desc()).limit(100)
    if company_id:
        await scoped_record(db, Company, company_id)
        query = query.where(ResearchJob.company_id == company_id)
    rows = (await db.scalars(query)).all()
    return [{"id": row.id, "company_id": row.company_id, "brain_version_id": row.brain_version_id, "status": row.status, "error_code": row.error_code} for row in rows]


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: UUID, db=Depends(get_workspace_db)):
    job = await db.scalar(select(ResearchJob).where(ResearchJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(404, "Research job not found")
    raise HTTPException(409, "Research execution requires an approved GTM plan and the durable worker")


@router.get("/jobs/{job_id}")
async def report(job_id: UUID, db=Depends(get_workspace_db)):
    job = await scoped_record(db, ResearchJob, job_id)
    intelligence = await db.scalar(select(AccountIntelligence).where(AccountIntelligence.job_id == job.id))
    claims = (await db.scalars(select(ResearchClaim).where(ResearchClaim.job_id == job.id))).all()
    evidence = []
    for claim in claims:
        review = await db.scalar(select(ClaimVerification).where(ClaimVerification.claim_id == claim.id).order_by(ClaimVerification.created_at.desc(), ClaimVerification.id.desc()).limit(1))
        item = await scoped_record(db, EvidenceItem, claim.evidence_id) if claim.evidence_id else None
        fetch = await scoped_record(db, SourceFetch, item.fetch_id) if item else None
        age_days = (datetime.utcnow() - fetch.retrieved_at).days if fetch else None
        evidence.append({"id": str(claim.id), "text": claim.text, "kind": "verified_fact" if review and review.decision == "verified" else claim.kind, "original_kind": claim.kind, "confidence": claim.confidence,
                         "review": {"decision": review.decision, "reason": review.reason, "method": "workspace_admin_review", "at": review.created_at} if review else None,
                         "model_version": claim.model_version, "excerpt": item.excerpt if item else None,
                         "url": fetch.url if fetch else None, "title": fetch.title if fetch else None,
                         "publisher": fetch.publisher if fetch else None, "published_at": fetch.published_at if fetch else None,
                         "retrieved_at": fetch.retrieved_at if fetch else None, "freshness": "stale" if age_days is not None and age_days > 30 else "recent_capture" if fetch else "unknown",
                         "content_hash": fetch.content_hash if fetch else None})
    return {"id": job.id, "status": job.status, "error_code": job.error_code,
            "intelligence": intelligence.result if intelligence else None, "claims": evidence}
