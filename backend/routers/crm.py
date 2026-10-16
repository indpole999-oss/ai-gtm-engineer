from backend.tenancy import require_approved_execution
from backend.tenancy import get_workspace_db as get_db
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import CRMRecord, Contact, Company
from backend.routers.auth import get_current_user
from agents.crm_agent import CRMAgent


router = APIRouter()
crm_agent = CRMAgent()


class CRMCreate(BaseModel):
    contact_id: UUID


class CRMCompanyCreate(BaseModel):
    company_id: UUID


class CRMDealCreate(BaseModel):
    deal_name: str
    amount: Optional[float] = None
    stage: Optional[str] = "appointmentscheduled"
    pipeline: Optional[str] = "default"
    close_date: Optional[str] = None
    company_id: Optional[UUID] = None


class CRMActivityCreate(BaseModel):
    record_id: str
    note: str


CRMDealCreate.model_rebuild()
CRMActivityCreate.model_rebuild()


@router.post("/deal", dependencies=[Depends(require_approved_execution)])
async def create_crm_deal(
    payload: CRMDealCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    company = None

    if payload.company_id:
        result = await db.execute(
            select(Company).where(
                Company.id == payload.company_id
            )
        )

        company = result.scalar_one_or_none()

        if not company:
            raise HTTPException(
                status_code=404,
                detail="Company not found",
            )

    context = {
        "user_id": str(current_user.id),
        "action": "create_deal",
        "deal": {
            "name": payload.deal_name,
            "amount": payload.amount,
            "stage": payload.stage,
            "pipeline": payload.pipeline,
            "close_date": payload.close_date,
        },
    }

    try:
        agent_result = await crm_agent.run(
            task="Create CRM deal",
            context=context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"CRM deal creation failed: {exc}",
        ) from exc

    if not isinstance(agent_result, dict):
        raise HTTPException(
            status_code=502,
            detail="CRM agent returned an invalid response",
        )

    status = str(
        agent_result.get("status", "")
    ).lower()

    if status in {
        "error",
        "failed",
        "failure",
    }:
        raise HTTPException(
            status_code=502,
            detail=agent_result,
        )

    if status in {
        "skipped",
        "not_configured",
    }:
        return {
            "status": "not_configured",
            "message": agent_result.get(
                "reason",
                agent_result.get(
                    "message",
                    "No CRM provider is connected.",
                ),
            ),
            "provider": agent_result.get(
                "provider"
            ),
            "deal_id": agent_result.get(
                "deal_id"
            ),
            "crm": agent_result,
        }

    return {
        "success": True,
        "provider": agent_result.get(
            "provider"
        ),
        "deal_id": agent_result.get(
            "deal_id"
        ),
        "status": agent_result.get(
            "status"
        ),
        "result": agent_result,
    }


@router.post("/activity", dependencies=[Depends(require_approved_execution)])
async def create_crm_activity(
    payload: CRMActivityCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = payload.note.strip()

    if not payload.record_id.strip():
        raise HTTPException(
            status_code=400,
            detail="CRM record ID is required",
        )

    if not note:
        raise HTTPException(
            status_code=400,
            detail="Activity note is required",
        )

    context = {
        "user_id": str(current_user.id),
        "action": "log_activity",
        "record_id": payload.record_id.strip(),
        "note": note,
    }

    try:
        agent_result = await crm_agent.run(
            task="Log CRM activity",
            context=context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"CRM activity logging failed: {exc}",
        ) from exc

    if not isinstance(agent_result, dict):
        raise HTTPException(
            status_code=502,
            detail="CRM agent returned an invalid response",
        )

    status = str(
        agent_result.get("status", "")
    ).lower()

    if status in {
        "error",
        "failed",
        "failure",
    }:
        raise HTTPException(
            status_code=502,
            detail=agent_result,
        )

    if status in {
        "skipped",
        "not_configured",
    }:
        return {
            "status": "not_configured",
            "message": agent_result.get(
                "reason",
                agent_result.get(
                    "message",
                    "No CRM provider is connected.",
                ),
            ),
            "provider": agent_result.get(
                "provider"
            ),
            "note_id": agent_result.get(
                "note_id"
            ),
            "crm": agent_result,
        }

    return {
        "success": True,
        "provider": agent_result.get(
            "provider"
        ),
        "note_id": agent_result.get(
            "note_id"
        ),
        "status": agent_result.get(
            "status"
        ),
        "result": agent_result,
    }


@router.get("/")
async def list_crm(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(CRMRecord)
    )

    records = result.scalars().all()

    data = []

    for r in records:
        item = {
            "id": str(r.id),
            "contact_id": str(r.contact_id),
            "stage": r.stage,
            "status": r.status,
            "notes": r.notes,
            "created_at": r.created_at,
        }

        for field in (
            "provider",
            "external_id",
            "crm_id",
            "synced_at",
        ):
            if hasattr(r, field):
                value = getattr(r, field)

                if value is not None:
                    item[field] = (
                        str(value)
                        if field in (
                            "external_id",
                            "crm_id",
                        )
                        else value
                    )

        data.append(item)

    return data


@router.post("/", dependencies=[Depends(require_approved_execution)])
async def create_crm_record(
    payload: CRMCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contact = await db.get(
        Contact,
        payload.contact_id,
    )

    if not contact:
        raise HTTPException(
            status_code=404,
            detail="Contact not found",
        )

    context = {
        "user_id": str(current_user.id),
        "contact_id": str(contact.id),
        "contact": {
            "id": str(contact.id),
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "email": contact.email,
            "title": getattr(
                contact,
                "title",
                None,
            ),
            "linkedin_url": getattr(
                contact,
                "linkedin_url",
                None,
            ),
            "phone": getattr(
                contact,
                "phone",
                None,
            ),
        },
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "title": getattr(
            contact,
            "title",
            None,
        ),
        "linkedin_url": getattr(
            contact,
            "linkedin_url",
            None,
        ),
        "phone": getattr(
            contact,
            "phone",
            None,
        ),
    }

    if getattr(
        contact,
        "company_id",
        None,
    ):
        company = await db.get(
            Company,
            contact.company_id,
        )

        if company:
            context["company"] = getattr(
                company,
                "name",
                None,
            )

            context["domain"] = getattr(
                company,
                "domain",
                None,
            )

    try:
        crm_result = await crm_agent.run(
            task="Create CRM record",
            context=context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"CRM agent failed: {exc}",
        ) from exc

    if not isinstance(
        crm_result,
        dict,
    ):
        raise HTTPException(
            status_code=502,
            detail="CRM agent returned an invalid response",
        )

    status = str(
        crm_result.get(
            "status",
            "",
        )
    ).lower()

    if status in {
        "error",
        "failed",
        "failure",
    }:
        raise HTTPException(
            status_code=502,
            detail=crm_result,
        )

    if status in {
        "skipped",
        "not_configured",
    }:
        return {
            "status": "not_configured",
            "message": crm_result.get(
                "reason",
                crm_result.get(
                    "message",
                    "No CRM provider is connected.",
                ),
            ),
            "contact_id": str(
                contact.id
            ),
            "provider": crm_result.get(
                "provider"
            ),
            "crm": crm_result,
        }

    provider = crm_result.get(
        "provider"
    )

    external_id = (
        crm_result.get("external_id")
        or crm_result.get("contact_id")
        or crm_result.get("crm_id")
        or crm_result.get("id")
    )

    # Prevent duplicate local CRM records for the same contact.
    # If an existing local record exists, update it instead of creating
    # another CRMRecord row.
    existing_result = await db.execute(
        select(CRMRecord)
        .where(
            CRMRecord.contact_id == contact.id
        )
        .order_by(
            CRMRecord.created_at.asc()
        )
    )

    crm = existing_result.scalars().first()

    created = False

    if crm is None:
        crm = CRMRecord(
            contact_id=contact.id,
            stage="new",
            status="active",
            notes=(
                "CRM record synchronized "
                "successfully"
            ),
        )

        db.add(crm)
        created = True

    else:
        crm.status = "active"
        crm.notes = (
            "CRM record synchronized "
            "successfully"
        )

    if (
        hasattr(crm, "provider")
        and provider
    ):
        crm.provider = provider

    if (
        hasattr(crm, "external_id")
        and external_id
    ):
        crm.external_id = str(
            external_id
        )

    if (
        hasattr(crm, "crm_id")
        and external_id
    ):
        crm.crm_id = str(
            external_id
        )

    if hasattr(
        crm,
        "synced_at",
    ):
        crm.synced_at = datetime.now(
            timezone.utc
        )

    await db.commit()
    await db.refresh(crm)

    return {
        "status": "success",
        "message": (
            "Contact pushed to CRM "
            "successfully"
        ),
        "crm_id": str(crm.id),
        "contact_id": str(contact.id),
        "provider": provider,
        "external_id": external_id,
        "created": created,
        "crm": crm_result,
    }


@router.post("/company", dependencies=[Depends(require_approved_execution)])
async def create_crm_company(
    payload: CRMCompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    company = await db.get(
        Company,
        payload.company_id,
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    company_data = {
        "id": str(company.id),
        "name": getattr(
            company,
            "name",
            None,
        ),
        "domain": getattr(
            company,
            "domain",
            None,
        ),
        "industry": getattr(
            company,
            "industry",
            None,
        ),
        "employee_count": getattr(
            company,
            "employee_count",
            None,
        ),
        "revenue": getattr(
            company,
            "revenue",
            None,
        ),
        "location": getattr(
            company,
            "location",
            None,
        ),
        "description": getattr(
            company,
            "description",
            None,
        ),
    }

    if not company_data["name"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Company name is required "
                "for CRM synchronization"
            ),
        )

    context = {
        "user_id": str(current_user.id),
        "company_id": str(company.id),
        "company": company_data,
        "name": company_data["name"],
        "domain": company_data["domain"],
        "industry": company_data["industry"],
        "employee_count": company_data[
            "employee_count"
        ],
        "revenue": company_data[
            "revenue"
        ],
        "location": company_data[
            "location"
        ],
        "description": company_data[
            "description"
        ],
        "action": "upsert_company",
    }

    try:
        crm_result = await crm_agent.run(
            task="Create CRM company",
            context=context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"CRM company sync failed: {exc}"
            ),
        ) from exc

    if not isinstance(
        crm_result,
        dict,
    ):
        raise HTTPException(
            status_code=502,
            detail="CRM agent returned an invalid response",
        )

    status = str(
        crm_result.get(
            "status",
            "",
        )
    ).lower()

    if status in {
        "error",
        "failed",
        "failure",
    }:
        raise HTTPException(
            status_code=502,
            detail=crm_result,
        )

    if status in {
        "skipped",
        "not_configured",
    }:
        return {
            "status": "not_configured",
            "message": crm_result.get(
                "reason",
                crm_result.get(
                    "message",
                    "No CRM provider is connected.",
                ),
            ),
            "company_id": str(
                company.id
            ),
            "provider": crm_result.get(
                "provider"
            ),
            "crm": crm_result,
        }

    provider = crm_result.get(
        "provider"
    )

    external_id = (
        crm_result.get("external_id")
        or crm_result.get("company_id")
        or crm_result.get("crm_id")
        or crm_result.get("id")
    )

    return {
        "status": "success",
        "message": (
            "Company pushed to CRM "
            "successfully"
        ),
        "company_id": str(
            company.id
        ),
        "provider": provider,
        "external_id": external_id,
        "crm": crm_result,
    }