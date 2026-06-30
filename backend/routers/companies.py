"""Companies router - CRUD for target companies"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List

from backend.database import get_db, Company
from backend.routers.auth import get_current_user

router = APIRouter()


class CompanyCreate(BaseModel):
      name: str
      domain: Optional[str] = None
      industry: Optional[str] = None
      employee_count: Optional[int] = None
      revenue: Optional[str] = None
      location: Optional[str] = None
      description: Optional[str] = None


@router.get("")
async def list_companies(
      skip: int = Query(0, ge=0),
      limit: int = Query(20, le=100),
      db: AsyncSession = Depends(get_db),
      current_user=Depends(get_current_user)
  ):
        result = await db.execute(select(Company).offset(skip).limit(limit))
        companies = result.scalars().all()
        return [{"id": str(c.id), "name": c.name, "domain": c.domain, "industry": c.industry} for c in companies]


@router.post("", status_code=201)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      company = Company(**data.model_dump())
      db.add(company)
      await db.flush()
      return {"id": str(company.id), "name": company.name, "message": "Company created"}


@router.get("/{company_id}")
async def get_company(company_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
      result = await db.execute(select(Company).where(Company.id == company_id))
      company = result.scalar_one_or_none()
      if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            return {"id": str(company.id), "name": company.name, "domain": company.domain, "industry": company.industry, "description": company.description}
