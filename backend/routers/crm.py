"""CRM Router - HubSpot integration for deal and contact management"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx

from backend.routers.auth import get_current_user
from backend.config import settings

router = APIRouter()


class DealCreate(BaseModel):
      deal_name: str
      contact_email: str
      amount: Optional[float] = None
      stage: str = "Prospecting"
      notes: Optional[str] = None


HUBSPOT_BASE = "https://api.hubapi.com/crm/v3"


@router.get("/contacts")
async def list_crm_contacts(current_user=Depends(get_current_user)):
      """Fetch contacts from HubSpot CRM"""
      async with httpx.AsyncClient() as client:
                resp = await client.get(
                              f"{HUBSPOT_BASE}/objects/contacts",
                              headers={"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}"}
                          )
            return resp.json()


@router.post("/deals")
async def create_crm_deal(deal: DealCreate, current_user=Depends(get_current_user)):
      """Create a deal in HubSpot CRM"""
    payload = {
              "properties": {
                            "dealname": deal.deal_name,
                            "dealstage": deal.stage,
                            "amount": str(deal.amount) if deal.amount else "0",
                            "description": deal.notes or "",
                        }
          }
    async with httpx.AsyncClient() as client:
              resp = await client.post(
                            f"{HUBSPOT_BASE}/objects/deals",
                            headers={"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}", "Content-Type": "application/json"},
                            json=payload
                        )
          return {"message": "Deal created in HubSpot", "data": resp.json()}
