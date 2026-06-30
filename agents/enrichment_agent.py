"""
Enrichment Agent - Company and contact data enrichment
Supports Apollo.io, Clearbit, and People Data Labs APIs
Steps 42-47: Lead enrichment, company data, contact discovery
"""
import httpx
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
CLEARBIT_API_KEY = os.getenv("CLEARBIT_API_KEY", "")
PDL_API_KEY = os.getenv("PDL_API_KEY", "")  # People Data Labs


class EnrichmentAgent:
  """Enriches company and contact data using Apollo, Clearbit, or PDL"""

  def __init__(self):
    self.apollo_key = APOLLO_API_KEY
    self.clearbit_key = CLEARBIT_API_KEY
    self.pdl_key = PDL_API_KEY

  # ── Apollo.io ────────────────────────────────────────────────────────────

  async def enrich_company_apollo(self, domain: str) -> Dict[str, Any]:
    """Enrich company data via Apollo Organizations API"""
    if not self.apollo_key:
      return {"status": "skipped", "reason": "APOLLO_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.apollo.io/v1/organizations/enrich",
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        json={"api_key": self.apollo_key, "domain": domain}
      )
      data = resp.json()
      org = data.get("organization", {})
      return {
        "source": "apollo",
        "name": org.get("name"),
        "domain": domain,
        "industry": org.get("industry"),
        "employee_count": org.get("estimated_num_employees"),
        "linkedin_url": org.get("linkedin_url"),
        "founded_year": org.get("founded_year"),
        "annual_revenue": org.get("annual_revenue_printed"),
        "hq_location": org.get("primary_domain"),
        "keywords": org.get("keywords", []),
        "technologies": org.get("technology_names", []),
        "status": "success"
      }

  async def find_contacts_apollo(self, domain: str, titles: Optional[List[str]] = None) -> List[Dict]:
    """Find decision-maker contacts at a company via Apollo People Search"""
    if not self.apollo_key:
      return []
    titles = titles or ["CEO", "CTO", "VP Sales", "Head of Engineering", "Founder"]
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.apollo.io/v1/mixed_people/search",
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        json={
          "api_key": self.apollo_key,
          "q_organization_domains": domain,
          "person_titles": titles,
          "per_page": 10
        }
      )
      data = resp.json()
      people = data.get("people", [])
      return [
        {
          "name": p.get("name"),
          "title": p.get("title"),
          "email": p.get("email"),
          "linkedin_url": p.get("linkedin_url"),
          "company": p.get("organization", {}).get("name")
        }
        for p in people
      ]

  # ── Clearbit ─────────────────────────────────────────────────────────────

  async def enrich_company_clearbit(self, domain: str) -> Dict[str, Any]:
    """Enrich company data via Clearbit Company API"""
    if not self.clearbit_key:
      return {"status": "skipped", "reason": "CLEARBIT_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.get(
        f"https://company.clearbit.com/v2/companies/find?domain={domain}",
        headers={"Authorization": f"Bearer {self.clearbit_key}"}
      )
      data = resp.json()
      return {
        "source": "clearbit",
        "name": data.get("name"),
        "domain": domain,
        "description": data.get("description"),
        "industry": data.get("category", {}).get("industry"),
        "employee_count": data.get("metrics", {}).get("employees"),
        "annual_revenue": data.get("metrics", {}).get("annualRevenue"),
        "linkedin_url": data.get("linkedin", {}).get("handle"),
        "technologies": data.get("tech", []),
        "status": "success"
      }

  # ── People Data Labs ──────────────────────────────────────────────────────

  async def enrich_person_pdl(self, email: str) -> Dict[str, Any]:
    """Enrich a contact by email via PDL Person Enrichment API"""
    if not self.pdl_key:
      return {"status": "skipped", "reason": "PDL_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.get(
        "https://api.peopledatalabs.com/v5/person/enrich",
        headers={"X-Api-Key": self.pdl_key},
        params={"email": email, "pretty": True}
      )
      data = resp.json()
      return {
        "source": "pdl",
        "name": data.get("full_name"),
        "email": email,
        "title": data.get("job_title"),
        "company": data.get("job_company_name"),
        "linkedin_url": data.get("linkedin_url"),
        "location": data.get("location_name"),
        "status": "success"
      }

  # ── Unified enrich ────────────────────────────────────────────────────────

  async def enrich_company(self, domain: str) -> Dict[str, Any]:
    """Try Apollo first, fallback to Clearbit"""
    if self.apollo_key:
      return await self.enrich_company_apollo(domain)
    elif self.clearbit_key:
      return await self.enrich_company_clearbit(domain)
    return {"status": "error", "reason": "No enrichment API key configured"}

  async def enrich_lead(self, domain: str, find_contacts: bool = True) -> Dict[str, Any]:
    """Full lead enrichment: company data + top decision makers"""
    company_data = await self.enrich_company(domain)
    contacts = []
    if find_contacts and self.apollo_key:
      contacts = await self.find_contacts_apollo(domain)
    return {
      "domain": domain,
      "company": company_data,
      "contacts": contacts,
      "status": "completed"
    }

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    domain = context.get("domain") if context else None
    email = context.get("email") if context else None
    action = context.get("action", "enrich_lead") if context else "enrich_lead"

    if action == "enrich_person" and email:
      return await self.enrich_person_pdl(email)
    elif action == "find_contacts" and domain:
      contacts = await self.find_contacts_apollo(domain)
      return {"domain": domain, "contacts": contacts, "status": "completed"}
    elif domain:
      return await self.enrich_lead(domain)
    return {"status": "error", "reason": "Missing domain or email in context"}
