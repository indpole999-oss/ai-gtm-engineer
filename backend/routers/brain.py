"""Reviewable Company Brain drafts and immutable published snapshots."""
import hashlib
import json
from datetime import datetime
from typing import Literal, Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from backend.brain_models import CompanyBrain, CompanyBrainVersion, CompanyBrainSource, BrainClaim
from backend.tenancy import get_current_workspace, get_workspace_db

router = APIRouter()
Short = Annotated[str, Field(max_length=4000)]


def extract_document(filename, raw):
    """Bounded document preview; never fetch links, execute macros or persist files."""
    from io import BytesIO
    from pathlib import Path
    from zipfile import ZipFile
    suffix = Path(filename or "").suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            content = raw.decode("utf-8-sig")
        elif suffix == ".pdf":
            from PyPDF2 import PdfReader
            document = PdfReader(BytesIO(raw))
            if document.is_encrypted or len(document.pages) > 50:
                raise ValueError("Unsupported PDF")
            content = "\n".join(page.extract_text() or "" for page in document.pages)
        elif suffix == ".docx":
            from docx import Document
            with ZipFile(BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 10000000:
                    raise ValueError("Document expansion limit")
            document = Document(BytesIO(raw))
            content = "\n".join(p.text for p in document.paragraphs)
        else:
            raise ValueError("Unsupported type")
        content = content.strip()
        if not content or len(content) > 100000:
            raise ValueError("Empty or oversized document")
        return {"title": Path(filename).name[:300], "content": content}
    except Exception:
        raise HTTPException(422, "Use a readable TXT, Markdown, DOCX or text PDF (up to 50 pages and 100,000 characters)") from None


@router.post("/documents/preview")
async def preview_document(file: UploadFile, db=Depends(get_workspace_db)):
    raw = await file.read(2000001)
    await file.close()
    if len(raw) > 2000000:
        raise HTTPException(413, "Document must be at most 2 MB")
    return await run_in_threadpool(extract_document, file.filename, raw)


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    company: Short = ""
    product_service: Short = ""
    value_proposition: Short = ""
    icp: Short = ""
    industries: Short = ""
    geographies: Short = ""
    buyer_personas: Short = ""
    pain_points: Short = ""
    competitors: Short = ""
    gtm_objectives: Short = ""
    positioning: Short = ""
    tone_guidance: Short = ""


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    kind: Literal["guided_answers", "website", "product_page", "case_study", "uploaded_document", "manual_edit", "crm_metadata"]
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl | None = None
    content: str = Field(min_length=1, max_length=100000)


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=4000)
    disposition: Literal["approved", "prohibited"]
    source_key: str | None = Field(None, max_length=80)


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    profile: Profile
    sources: list[SourceInput] = Field(default_factory=list, max_length=30)
    claims: list[ClaimInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_sources(self):
        keys = [source.key for source in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError("Source keys must be unique")
        if sum(len(s.content) for s in self.sources) > 500000:
            raise ValueError("Source content exceeds 500,000 characters")
        for claim in self.claims:
            if claim.source_key and claim.source_key not in keys:
                raise ValueError("Claim source must belong to this version")
        return self


class PublishInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    reviewed: Literal[True]


async def find_version(db, version_id, lock=False):
    query = select(CompanyBrainVersion).where(CompanyBrainVersion.id == version_id)
    if lock:
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Company Brain version not found")
    return row


async def snapshot(db, version):
    sources = (await db.scalars(select(CompanyBrainSource).where(CompanyBrainSource.version_id == version.id).order_by(CompanyBrainSource.key))).all()
    claims = (await db.scalars(select(BrainClaim).where(BrainClaim.version_id == version.id).order_by(BrainClaim.disposition, BrainClaim.text))).all()
    return {"id": str(version.id), "number": version.number, "status": version.status,
            "revision": version.revision, "profile": version.profile,
            "content_hash": version.content_hash, "published_at": version.published_at,
            "sources": [{"key": s.key, "kind": s.kind, "title": s.title, "url": s.url, "content": s.content} for s in sources],
            "claims": [{"text": c.text, "disposition": c.disposition, "source_key": c.source_key} for c in claims]}


@router.get("")
async def list_versions(db=Depends(get_workspace_db)):
    rows = (await db.scalars(select(CompanyBrainVersion).order_by(CompanyBrainVersion.number.desc()))).all()
    return {"versions": [{"id": str(v.id), "number": v.number, "status": v.status, "published_at": v.published_at} for v in rows]}


@router.get("/versions/{version_id}")
async def get_version(version_id: UUID, db=Depends(get_workspace_db)):
    return await snapshot(db, await find_version(db, version_id))


@router.post("/drafts", status_code=201)
async def create_draft(ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    brain = await db.scalar(select(CompanyBrain).with_for_update())
    if not brain:
        brain = CompanyBrain(workspace_id=ctx.workspace_id)
        db.add(brain)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "Company Brain changed; reload and retry") from None
    latest = await db.scalar(select(CompanyBrainVersion).where(CompanyBrainVersion.brain_id == brain.id).order_by(CompanyBrainVersion.number.desc()).limit(1))
    if latest and latest.status == "draft":
        return await snapshot(db, latest)
    previous = await snapshot(db, latest) if latest else None
    row = CompanyBrainVersion(brain_id=brain.id, number=latest.number + 1 if latest else 1,
                              profile=latest.profile if latest else Profile().model_dump(), created_by=ctx.user_id)
    db.add(row)
    try:
        await db.flush()
        if previous:
            await replace_content(db, row, previous["sources"], previous["claims"])
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Company Brain changed; reload and retry") from None
    return await snapshot(db, row)


async def replace_content(db, row, sources, claims):
    for model in (BrainClaim, CompanyBrainSource):
        for old in (await db.scalars(select(model).where(model.version_id == row.id))).all():
            await db.delete(old)
        await db.flush()
    for source in sources:
        db.add(CompanyBrainSource(version_id=row.id, **source,
                                 content_hash=hashlib.sha256(source["content"].encode()).hexdigest()))
    await db.flush()
    for claim in claims:
        db.add(BrainClaim(version_id=row.id, **claim))
    await db.flush()


@router.put("/versions/{version_id}")
async def update_draft(version_id: UUID, body: DraftInput, db=Depends(get_workspace_db)):
    row = await find_version(db, version_id, True)
    if row.status != "draft" or row.revision != body.revision:
        raise HTTPException(409, "Version is published or changed; reload before editing")
    row.profile = body.profile.model_dump()
    # Increment even for source-only edits, so every edit participates in CAS.
    row.revision += 1
    try:
        await replace_content(db, row, [s.model_dump(mode="json") for s in body.sources], [c.model_dump() for c in body.claims])
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(409, "Draft changed; reload before editing") from None
    return await snapshot(db, row)


@router.post("/versions/{version_id}/publish")
async def publish(version_id: UUID, body: PublishInput, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    ctx.require("owner", "admin")
    row = await find_version(db, version_id, True)
    if row.status != "draft" or row.revision != body.revision:
        raise HTTPException(409, "Version is published or changed; review the current draft")
    required = ("company", "product_service", "value_proposition", "icp", "buyer_personas", "gtm_objectives")
    missing = [key for key in required if not row.profile.get(key, "").strip()]
    if missing:
        raise HTTPException(422, "Complete these fields before publishing: " + ", ".join(missing))
    data = await snapshot(db, row)
    canonical = {key: data[key] for key in ("profile", "sources", "claims")}
    row.content_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    row.status, row.published_by, row.published_at = "published", ctx.user_id, datetime.utcnow()
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(409, "Draft changed; review before publishing") from None
    return await snapshot(db, row)
