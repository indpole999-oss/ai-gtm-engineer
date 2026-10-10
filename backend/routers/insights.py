"""Advisory analytics only. No mutation or execution endpoints."""
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends
from backend.tenancy import get_workspace_db
from backend.insights_service import report

router = APIRouter()


@router.get("")
async def insights(start: datetime, end: datetime, entity_type: Literal["account", "contact"] = "contact", db=Depends(get_workspace_db)):
    return await report(db, start, end, entity_type)
