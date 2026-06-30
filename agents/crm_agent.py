"""
CRM Agent - HubSpot and Salesforce CRM integration
Steps 59-65: Contact creation, activity logging, deal management, pipeline updates
"""
import httpx
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# CRM provider config
CRM_PROVIDER = os.getenv("CRM_PROVIDER", "hubspot")  # hubspot | salesforce
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "")  # Private App Token
SALESFORCE_INSTANCE_URL = os.getenv("SALESFORCE_INSTANCE_URL", "")
SALESFORCE_ACCESS_TOKEN = os.getenv("SALESFORCE_ACCESS_TOKEN", "")


class CRMAgent:
  """Manages CRM operations: contacts, activities, deals, pipeline updates"""

  def __init__(self):
    self.provider = CRM_PROVIDER
    self.hubspot_key = HUBSPOT_API_KEY
    self.sf_url = SALESFORCE_INSTANCE_URL
    self.sf_token = SALESFORCE_ACCESS_TOKEN

  # ── HubSpot ─────────────────────────────────────────────────────────────────

  def _hs_headers(self) -> Dict:
    return {"Authorization": f"Bearer {self.hubspot_key}", "Content-Type": "application/json"}

  async def create_contact_hubspot(self, contact: Dict) -> Dict:
    """Create or update a contact in HubSpot"""
    payload = {
      "properties": {
        "firstname": contact.get("first_name", ""),
        "lastname": contact.get("last_name", ""),
        "email": contact.get("email", ""),
        "jobtitle": contact.get("title", ""),
        "company": contact.get("company", ""),
        "website": contact.get("domain", ""),
        "linkedin_url": contact.get("linkedin_url", "")
      }
    }
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.hubapi.com/crm/v3/objects/contacts",
        headers=self._hs_headers(),
        json=payload
      )
      data = resp.json()
      return {
        "provider": "hubspot",
        "contact_id": data.get("id"),
        "status": "created" if resp.status_code == 201 else "failed",
        "raw": data
      }

  async def log_activity_hubspot(self, contact_id: str, note: str, activity_type: str = "NOTE") -> Dict:
    """Log a note/activity against a HubSpot contact"""
    payload = {
      "properties": {
        "hs_note_body": note,
        "hs_timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
      },
      "associations": [{
        "to": {"id": contact_id},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
      }]
    }
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.hubapi.com/crm/v3/objects/notes",
        headers=self._hs_headers(),
        json=payload
      )
      data = resp.json()
      return {"provider": "hubspot", "note_id": data.get("id"), "status": "logged" if resp.status_code == 201 else "failed"}

  async def create_deal_hubspot(self, deal: Dict, contact_id: Optional[str] = None) -> Dict:
    """Create a deal in HubSpot pipeline"""
    payload = {
      "properties": {
        "dealname": deal.get("name", ""),
        "dealstage": deal.get("stage", "appointmentscheduled"),
        "pipeline": deal.get("pipeline", "default"),
        "amount": str(deal.get("amount", "")),
        "closedate": deal.get("close_date", "")
      }
    }
    if contact_id:
      payload["associations"] = [{
        "to": {"id": contact_id},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
      }]
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.hubapi.com/crm/v3/objects/deals",
        headers=self._hs_headers(),
        json=payload
      )
      data = resp.json()
      return {"provider": "hubspot", "deal_id": data.get("id"), "status": "created" if resp.status_code == 201 else "failed"}

  async def search_contact_hubspot(self, email: str) -> Optional[Dict]:
    """Find a contact by email in HubSpot"""
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.hubapi.com/crm/v3/objects/contacts/search",
        headers=self._hs_headers(),
        json={"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}]}
      )
      data = resp.json()
      results = data.get("results", [])
      return results[0] if results else None

  # ── Salesforce ──────────────────────────────────────────────────────────────

  def _sf_headers(self) -> Dict:
    return {"Authorization": f"Bearer {self.sf_token}", "Content-Type": "application/json"}

  async def create_lead_salesforce(self, contact: Dict) -> Dict:
    """Create a Lead record in Salesforce"""
    payload = {
      "FirstName": contact.get("first_name", ""),
      "LastName": contact.get("last_name", contact.get("name", "Unknown")),
      "Email": contact.get("email", ""),
      "Title": contact.get("title", ""),
      "Company": contact.get("company", "Unknown"),
      "Website": contact.get("domain", "")
    }
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        f"{self.sf_url}/services/data/v58.0/sobjects/Lead",
        headers=self._sf_headers(),
        json=payload
      )
      data = resp.json()
      return {"provider": "salesforce", "lead_id": data.get("id"), "status": "created" if data.get("success") else "failed"}

  async def log_task_salesforce(self, who_id: str, subject: str, description: str) -> Dict:
    """Log an activity task against a Salesforce record"""
    payload = {
      "Subject": subject,
      "Description": description,
      "WhoId": who_id,
      "Status": "Completed",
      "ActivityDate": __import__("datetime").date.today().isoformat()
    }
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        f"{self.sf_url}/services/data/v58.0/sobjects/Task",
        headers=self._sf_headers(),
        json=payload
      )
      data = resp.json()
      return {"provider": "salesforce", "task_id": data.get("id"), "status": "created" if data.get("success") else "failed"}

  # ── Unified CRM ──────────────────────────────────────────────────────────────

  async def upsert_contact(self, contact: Dict) -> Dict:
    """Create contact in configured CRM provider"""
    if self.provider == "hubspot" and self.hubspot_key:
      return await self.create_contact_hubspot(contact)
    elif self.provider == "salesforce" and self.sf_token:
      return await self.create_lead_salesforce(contact)
    return {"status": "skipped", "reason": "No CRM provider configured"}

  async def log_activity(self, record_id: str, note: str) -> Dict:
    """Log activity in configured CRM provider"""
    if self.provider == "hubspot" and self.hubspot_key:
      return await self.log_activity_hubspot(record_id, note)
    elif self.provider == "salesforce" and self.sf_token:
      return await self.log_task_salesforce(record_id, "GTM Agent Activity", note)
    return {"status": "skipped", "reason": "No CRM provider configured"}

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    action = context.get("action", "upsert_contact") if context else "upsert_contact"
    contact = context.get("contact", {}) if context else {}
    record_id = context.get("record_id") if context else None
    note = context.get("note", "") if context else ""
    deal = context.get("deal", {}) if context else {}

    if action == "upsert_contact":
      return await self.upsert_contact(contact)
    elif action == "log_activity" and record_id:
      return await self.log_activity(record_id, note)
    elif action == "create_deal" and self.provider == "hubspot":
      return await self.create_deal_hubspot(deal, record_id)
    elif action == "search_contact":
      email = context.get("email") if context else None
      result = await self.search_contact_hubspot(email) if email else None
      return {"contact": result, "found": result is not None}
    elif action == "full_intake":
      # Create contact + log initial activity
      crm_result = await self.upsert_contact(contact)
      if crm_result.get("contact_id") or crm_result.get("lead_id"):
        rid = crm_result.get("contact_id") or crm_result.get("lead_id")
        await self.log_activity(rid, note or f"Lead added via AI GTM Engineer for {contact.get('company')}")
      return {"crm_result": crm_result, "status": "completed"}

    return {"status": "error", "reason": f"Unknown action: {action}"}
