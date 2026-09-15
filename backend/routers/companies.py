from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID

from backend.database import Company, get_db
from backend.routers.auth import get_current_user

router = APIRouter()


# ---------- SCHEMA ----------

class CompanyCreate(BaseModel):
    name: str
    domain: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue: str | None = None
    location: str | None = None
    description: str | None = None
    extra_data: dict = {}


# ---------- RESPONSE HELPER ----------

def company_response(company: Company):
    return {
        "id": str(company.id),
        "name": company.name,
        "domain": company.domain,
        "industry": company.industry,
        "employee_count": company.employee_count,
        "revenue": company.revenue,
        "location": company.location,
        "description": company.description,
        "extra_data": company.extra_data or {},
        "created_at": (
            company.created_at.isoformat()
            if company.created_at
            else None
        ),
    }


# ---------- CREATE COMPANY ----------

@router.post("/")
async def create_company(
    company: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    new_company = Company(
        name=company.name,
        domain=company.domain,
        industry=company.industry,
        employee_count=company.employee_count,
        revenue=company.revenue,
        location=company.location,
        description=company.description,
        extra_data=company.extra_data,
    )

    db.add(new_company)

    await db.commit()
    await db.refresh(new_company)

    return company_response(new_company)


# ---------- LIST COMPANIES ----------

@router.get("/")
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Company))
    companies = result.scalars().all()

    return [
        company_response(company)
        for company in companies
    ]


# ---------- GET COMPANY BY ID ----------

@router.get("/{company_id}")
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Company).where(Company.id == company_id)
    )

    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return company_response(company)
    new_company = Company(
        name=company.name,
        domain=company.domain,
        industry=company.industry,
        employee_count=company.employee_count,
        revenue=company.revenue,
        location=company.location,
        description=company.description,
        extra_data=company.extra_data,
    )

    db.add(new_company)

    await db.commit()
    await db.refresh(new_company)

    return company_response(new_company)


# ---------- LIST COMPANIES ----------

@router.get("/")
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Company))
    companies = result.scalars().all()

    return [
        company_response(company)
        for company in companies
    ]


# ---------- GET COMPANY BY ID ----------

@router.get("/{company_id}")
async def get_company(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Company).where(Company.id == company_id)
    )

    company = result.scalar_one_or_none()

    if not company:
        return {
            "error": "Company not found"
        }

    return company_response(company)