"""Safe local record operations, shared by the existing V1 resource routes."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from backend.database import Company, Contact, CRMRecord, EmailLog, Meeting
from backend.tenancy import get_workspace_db

router = APIRouter()


class CompanyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class ContactPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None


async def find_record(db, model, record_id):
    record = await db.scalar(select(model).where(model.id == record_id))
    if record is None:
        raise HTTPException(404, "Record not found")
    return record


def add_record_routes(path, model):
    async def read_record(record_id: UUID, db=Depends(get_workspace_db)):
        return await find_record(db, model, record_id)

    async def delete_record(record_id: UUID, db=Depends(get_workspace_db)):
        record = await find_record(db, model, record_id)
        if model in (Company, Contact):
            from backend.outcome_models import PipelineRecord
            field = PipelineRecord.company_id if model is Company else PipelineRecord.contact_id
            if await db.scalar(select(PipelineRecord.id).where(field == record_id).limit(1)):
                raise HTTPException(409, "Retained pipeline history references this record; deletion is blocked")
        await db.delete(record)
        await db.flush()
        return {"status": "deleted"}

    if model not in (Company, Contact):
        router.add_api_route(f"/{path}/{{record_id}}", read_record, methods=["GET"], name=f"read_{path}")
    router.add_api_route(f"/{path}/{{record_id}}", delete_record, methods=["DELETE"], name=f"delete_{path}")


for path, model in (("companies", Company), ("contacts", Contact), ("crm", CRMRecord), ("emails", EmailLog), ("calendar", Meeting)):
    add_record_routes(path, model)


@router.patch("/companies/{record_id}")
async def update_company(record_id: UUID, payload: CompanyPatch, db=Depends(get_workspace_db)):
    record = await find_record(db, Company, record_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "name" and value is None:
            raise HTTPException(422, "Company name cannot be null")
        setattr(record, key, value)
    await db.flush()
    return record


@router.patch("/contacts/{record_id}")
async def update_contact(record_id: UUID, payload: ContactPatch, db=Depends(get_workspace_db)):
    record = await find_record(db, Contact, record_id)
    if "company_id" in payload.model_fields_set and payload.company_id != record.company_id:
        if payload.company_id:
            await find_record(db, Company, payload.company_id)
        from backend.outcome_models import PipelineRecord
        if await db.scalar(select(PipelineRecord.id).where(PipelineRecord.contact_id == record.id)):
            raise HTTPException(409, "Retained pipeline history fixes this prospect account; create a separate prospect record")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await db.flush()
    return record
