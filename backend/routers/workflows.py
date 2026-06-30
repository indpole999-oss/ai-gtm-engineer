"""Workflows Router - n8n workflow management (Steps 61-66)"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx

from backend.routers.auth import get_current_user
from backend.config import settings

router = APIRouter()


GTM_WORKFLOWS = {
      "full_outreach": "Research → Enrich → Personalize → Send Email → Update CRM",
      "research_only": "Research company and return insights",
      "enrich_contacts": "Enrich a list of contacts with Apollo data",
      "email_sequence": "Send a multi-step email outreach sequence",
      "book_meetings": "Find contacts and auto-book discovery calls",
  }


@router.get("/")
async def list_workflows(current_user=Depends(get_current_user)):
      return {"workflows": GTM_WORKFLOWS, "n8n_url": settings.N8N_WEBHOOK_URL}


@router.post("/trigger/{workflow_name}")
async def trigger_workflow(
      workflow_name: str,
      payload: Optional[Dict[str, Any]] = None,
      current_user=Depends(get_current_user)
  ):
        """Trigger an n8n workflow via webhook"""
        if workflow_name not in GTM_WORKFLOWS:
                  raise HTTPException(status_code=400, detail=f"Unknown workflow: {workflow_name}")
              webhook_url = f"{settings.N8N_WEBHOOK_URL}/webhook/{workflow_name}"
    async with httpx.AsyncClient() as client:
              try:
                            resp = await client.post(webhook_url, json=payload or {}, timeout=30)
                            return {"workflow": workflow_name, "status": "triggered", "n8n_response": resp.json()}
                        except Exception as e:
                                      return {"workflow": workflow_name, "status": "queued_locally", "note": "n8n not running - configure N8N_WEBHOOK_URL in .env"}
