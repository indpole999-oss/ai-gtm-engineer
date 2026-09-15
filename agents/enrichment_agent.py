"""
Enrichment Agent - Company and Contact Enrichment

Supports:
- Apollo.io
- Clearbit
- People Data Labs
- Free public search fallback
- BrowserAgent / Playwright website enrichment

Stage 9 Compatible
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv

from agents.browser_agent import BrowserAgent


load_dotenv()


logger = logging.getLogger(__name__)


# ============================================================
# Environment Configuration
# ============================================================

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "").strip()
CLEARBIT_API_KEY = os.getenv("CLEARBIT_API_KEY", "").strip()
PDL_API_KEY = os.getenv("PDL_API_KEY", "").strip()


# ============================================================
# Enrichment Agent
# ============================================================

class EnrichmentAgent:

    def __init__(self):
        self.apollo_key = APOLLO_API_KEY
        self.clearbit_key = CLEARBIT_API_KEY
        self.pdl_key = PDL_API_KEY
        self.browser_agent = BrowserAgent()

    # ========================================================
    # Utility: Normalize Domain
    # ========================================================

    @staticmethod
    def _normalize_domain(
        domain: Optional[str]
    ) -> Optional[str]:

        if not domain:
            return None

        domain = str(domain).strip().lower()

        domain = re.sub(
            r"^https?://",
            "",
            domain
        )

        domain = re.sub(
            r"^www\.",
            "",
            domain
        )

        domain = domain.split("/", 1)[0]
        domain = domain.split("?", 1)[0]
        domain = domain.split("#", 1)[0]
        domain = domain.rstrip(".")

        return domain or None

    # ========================================================
    # Utility: Website URL
    # ========================================================

    @staticmethod
    def _website_url(
        domain: str
    ) -> str:

        clean_domain = EnrichmentAgent._normalize_domain(
            domain
        )

        if not clean_domain:
            return ""

        return f"https://{clean_domain}"

    # ========================================================
    # Utility: Extract Emails
    # ========================================================

    @staticmethod
    def _extract_emails(
        content: str,
        domain: Optional[str] = None
    ) -> List[str]:

        if not content:
            return []

        emails = re.findall(
            r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
            content
        )

        clean_domain = EnrichmentAgent._normalize_domain(
            domain
        )

        results: List[str] = []
        seen = set()

        ignored_prefixes = (
            "example@",
            "test@",
            "noreply@",
            "no-reply@",
            "donotreply@",
            "do-not-reply@"
        )

        for email in emails:

            email = email.strip().lower()

            if not email:
                continue

            if email in seen:
                continue

            if email.startswith(ignored_prefixes):
                continue

            if clean_domain:
                email_domain = email.split(
                    "@",
                    1
                )[1]

                if email_domain != clean_domain:
                    continue

            seen.add(email)
            results.append(email)

        return results

    # ========================================================
    # Utility: Convert Email Into Possible Name
    # ========================================================

    @staticmethod
    def _name_from_email(
        email: str
    ) -> str:

        if not email or "@" not in email:
            return ""

        local_part = email.split(
            "@",
            1
        )[0]

        name = (
            local_part
            .replace(".", " ")
            .replace("_", " ")
            .replace("-", " ")
        )

        return name.title().strip()

    # ========================================================
    # Utility: Deduplicate Contacts
    # ========================================================

    @staticmethod
    def _deduplicate_contacts(
        contacts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        unique: List[Dict[str, Any]] = []

        seen_emails = set()
        seen_linkedin = set()

        for contact in contacts:

            if not isinstance(contact, dict):
                continue

            email = (
                str(
                    contact.get("email") or ""
                )
                .strip()
                .lower()
            )

            linkedin = (
                str(
                    contact.get("linkedin_url") or ""
                )
                .strip()
                .lower()
            )

            if email and email in seen_emails:
                continue

            if linkedin and linkedin in seen_linkedin:
                continue

            if email:
                seen_emails.add(email)

            if linkedin:
                seen_linkedin.add(linkedin)

            unique.append(contact)

        return unique

    # ========================================================
    # Apollo Company Enrichment
    # ========================================================

    async def enrich_company_apollo(
        self,
        domain: str
    ) -> Dict[str, Any]:

        if not self.apollo_key:
            return {
                "status": "skipped",
                "source": "apollo",
                "reason": "APOLLO_API_KEY not configured"
            }

        domain = self._normalize_domain(domain)

        if not domain:
            return {
                "status": "error",
                "source": "apollo",
                "reason": "Invalid domain"
            }

        try:

            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True
            ) as client:

                response = await client.post(
                    "https://api.apollo.io/v1/organizations/enrich",
                    headers={
                        "Content-Type": "application/json",
                        "X-Api-Key": self.apollo_key
                    },
                    json={
                        "domain": domain
                    }
                )

                logger.info(
                    "Apollo Company Status: %s",
                    response.status_code
                )

                try:
                    data = response.json()
                except Exception:
                    data = {
                        "raw_response": response.text
                    }

                if response.status_code != 200:
                    return {
                        "status": "error",
                        "source": "apollo",
                        "status_code": response.status_code,
                        "reason": data
                    }

                organization = data.get(
                    "organization",
                    {}
                )

                if not organization:
                    return {
                        "status": "error",
                        "source": "apollo",
                        "reason": "No organization data returned"
                    }

                technology_names = (
                    organization.get(
                        "technology_names",
                        []
                    )
                    or []
                )

                return {
                    "status": "success",
                    "source": "apollo",
                    "company": {
                        "name": organization.get(
                            "name"
                        ),
                        "domain": (
                            organization.get(
                                "primary_domain"
                            )
                            or domain
                        ),
                        "website": (
                            organization.get(
                                "website_url"
                            )
                            or self._website_url(domain)
                        ),
                        "industry": organization.get(
                            "industry"
                        ),
                        "employees": organization.get(
                            "estimated_num_employees"
                        ),
                        "revenue": organization.get(
                            "annual_revenue_printed"
                        ),
                        "linkedin": organization.get(
                            "linkedin_url"
                        ),
                        "location": {
                            "city": organization.get(
                                "city"
                            ),
                            "state": organization.get(
                                "state"
                            ),
                            "country": organization.get(
                                "country"
                            )
                        },
                        "technologies": technology_names[:25]
                    }
                }

        except httpx.TimeoutException:

            logger.warning(
                "Apollo company enrichment timed out for %s",
                domain
            )

            return {
                "status": "error",
                "source": "apollo",
                "reason": "Apollo API request timed out"
            }

        except httpx.HTTPError as e:

            logger.warning(
                "Apollo company HTTP error for %s: %s",
                domain,
                e
            )

            return {
                "status": "error",
                "source": "apollo",
                "reason": str(e)
            }

        except Exception as e:

            logger.exception(
                "Apollo company enrichment failed for %s",
                domain
            )

            return {
                "status": "error",
                "source": "apollo",
                "reason": str(e)
            }

    # ========================================================
    # Apollo Contact Enrichment
    # ========================================================

    async def find_contacts_apollo(
        self,
        domain: str,
        titles: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:

        if not self.apollo_key:
            return []

        domain = self._normalize_domain(domain)

        if not domain:
            return []

        titles = titles or [
            "CEO",
            "Founder",
            "Co-Founder",
            "CTO",
            "VP Sales",
            "Head of Sales",
            "Head of Engineering",
            "VP Engineering",
            "Chief Technology Officer",
            "Chief Executive Officer"
        ]

        try:

            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True
            ) as client:

                response = await client.post(
                    "https://api.apollo.io/v1/mixed_people/search",
                    headers={
                        "Content-Type": "application/json",
                        "X-Api-Key": self.apollo_key
                    },
                    json={
                        "q_organization_domains": [domain],
                        "person_titles": titles,
                        "page": 1,
                        "per_page": 10
                    }
                )

                try:
                    data = response.json()
                except Exception:
                    data = {}

                if response.status_code != 200:

                    logger.warning(
                        "Apollo contact search unavailable: %s",
                        data
                    )

                    return []

                contacts: List[Dict[str, Any]] = []

                for person in data.get(
                    "people",
                    []
                ) or []:

                    if not isinstance(person, dict):
                        continue

                    name = (
                        person.get("name")
                        or "Unknown"
                    )

                    organization_name = (
                        person.get(
                            "organization_name"
                        )
                        or person.get(
                            "company"
                        )
                    )

                    contact = {
                        "name": name,
                        "first_name": person.get(
                            "first_name"
                        ),
                        "last_name": person.get(
                            "last_name"
                        ),
                        "title": person.get(
                            "title"
                        ),
                        "email": person.get(
                            "email"
                        ),
                        "linkedin_url": person.get(
                            "linkedin_url"
                        ),
                        "company": organization_name,
                        "domain": domain,
                        "source": "apollo"
                    }

                    contacts.append(contact)

                contacts = self._deduplicate_contacts(
                    contacts
                )

                logger.info(
                    "Apollo returned %s contacts for %s",
                    len(contacts),
                    domain
                )

                return contacts[:20]

        except httpx.TimeoutException:

            logger.warning(
                "Apollo contact search timed out for %s",
                domain
            )

            return []

        except httpx.HTTPError as e:

            logger.warning(
                "Apollo contact HTTP error for %s: %s",
                domain,
                e
            )

            return []

        except Exception as e:

            logger.exception(
                "Apollo contact search failed for %s",
                domain
            )

            return []

    # ========================================================
    # FREE PUBLIC SEARCH CONTACT DISCOVERY
    # ========================================================

    async def find_contacts_search(
        self,
        domain: str
    ) -> List[Dict[str, Any]]:

        """
        Free public-search fallback.

        Does not require Apollo, Serper or Tavily API keys.

        Uses DuckDuckGo public HTML search to discover
        publicly indexed company email addresses and
        LinkedIn profile signals.

        Apollo remains the primary contact provider.
        """

        domain = self._normalize_domain(domain)

        if not domain:
            return []

        queries = [
            f'site:{domain} "@{domain}"',
            f'site:{domain} contact email',
            f'site:{domain} sales email',
            f'site:{domain} founder',
            f'site:{domain} leadership',
            f'site:linkedin.com/in "{domain}"'
        ]

        contacts: List[Dict[str, Any]] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:

            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers=headers
            ) as client:

                for query in queries:

                    try:

                        search_url = (
                            "https://html.duckduckgo.com/html/"
                            f"?q={quote_plus(query)}"
                        )

                        response = await client.get(
                            search_url
                        )

                        if response.status_code != 200:
                            logger.warning(
                                "Free search returned HTTP %s",
                                response.status_code
                            )
                            continue

                        html = response.text

                        # ------------------------------------------------
                        # Extract emails from search result HTML
                        # ------------------------------------------------

                        emails = self._extract_emails(
                            html,
                            domain
                        )

                        for email in emails:

                            name = self._name_from_email(
                                email
                            )

                            parts = name.split()

                            contacts.append({
                                "name": name,
                                "first_name": (
                                    parts[0]
                                    if parts
                                    else None
                                ),
                                "last_name": (
                                    " ".join(parts[1:])
                                    if len(parts) > 1
                                    else None
                                ),
                                "title": None,
                                "email": email,
                                "linkedin_url": None,
                                "company": None,
                                "domain": domain,
                                "source": "public_search",
                                "source_url": search_url,
                                "confidence": "public"
                            })

                        # ------------------------------------------------
                        # Extract LinkedIn profile URLs
                        # ------------------------------------------------

                        linkedin_urls = re.findall(
                            r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_%\-]+",
                            html,
                            flags=re.IGNORECASE
                        )

                        for linkedin_url in linkedin_urls:

                            linkedin_url = (
                                linkedin_url
                                .replace(
                                    "&amp;",
                                    "&"
                                )
                            )

                            contacts.append({
                                "name": self._guess_name_from_linkedin(
                                    linkedin_url
                                ),
                                "first_name": None,
                                "last_name": None,
                                "title": None,
                                "email": None,
                                "linkedin_url": linkedin_url,
                                "company": None,
                                "domain": domain,
                                "source": "public_search",
                                "source_url": search_url,
                                "confidence": "public"
                            })

                        contacts = self._deduplicate_contacts(
                            contacts
                        )

                        # Stop once useful contacts are discovered.
                        if any(
                            contact.get("email")
                            for contact in contacts
                        ):
                            break

                    except Exception as e:

                        logger.warning(
                            "Free search query failed for %s: %s",
                            query,
                            e
                        )

                        continue

        except Exception as e:

            logger.warning(
                "Free public contact discovery failed for %s: %s",
                domain,
                e
            )

            return []

        contacts = self._deduplicate_contacts(
            contacts
        )

        logger.info(
            "Free public search discovered %s contacts for %s",
            len(contacts),
            domain
        )

        return contacts[:20]

    # ========================================================
    # Browser Company Enrichment
    # ========================================================

    async def enrich_company_browser(
        self,
        domain: str
    ) -> Dict[str, Any]:

        domain = self._normalize_domain(domain)

        if not domain:
            return {
                "status": "error",
                "source": "browser",
                "reason": "Invalid domain"
            }

        try:

            result = await self.browser_agent.extract_company_info(
                domain
            )

            if not isinstance(result, dict):
                return {
                    "status": "failed",
                    "source": "browser",
                    "reason": (
                        "BrowserAgent returned invalid response"
                    )
                }

            if result.get("status") != "success":
                return {
                    "status": "failed",
                    "source": "browser",
                    "reason": result.get(
                        "error",
                        result.get(
                            "reason",
                            "Unable to access company website"
                        )
                    )
                }

            return {
                "status": "success",
                "source": "browser",
                "company": {
                    "domain": domain,
                    "website": self._website_url(
                        domain
                    ),
                    "title": result.get(
                        "title"
                    ),
                    "homepage_text": result.get(
                        "homepage_text",
                        ""
                    )
                }
            }

        except Exception as e:

            logger.exception(
                "Browser company enrichment failed for %s",
                domain
            )

            return {
                "status": "error",
                "source": "browser",
                "reason": str(e)
            }

    # ========================================================
    # Browser Contact Extraction From Text
    # ========================================================

    def extract_contacts_from_text(
        self,
        content: str,
        domain: str
    ) -> List[Dict[str, Any]]:

        if not content:
            return []

        domain = self._normalize_domain(
            domain
        )

        emails = self._extract_emails(
            content,
            domain
        )

        contacts: List[Dict[str, Any]] = []

        for email in emails:

            name = self._name_from_email(
                email
            )

            name_parts = name.split()

            contacts.append({
                "name": name,
                "first_name": (
                    name_parts[0]
                    if name_parts
                    else None
                ),
                "last_name": (
                    " ".join(name_parts[1:])
                    if len(name_parts) > 1
                    else None
                ),
                "title": None,
                "email": email,
                "linkedin_url": None,
                "company": None,
                "domain": domain,
                "source": "browser"
            })

        return self._deduplicate_contacts(
            contacts
        )

    # ========================================================
    # Browser Contact Page Discovery
    # ========================================================

    async def find_contacts_browser(
        self,
        domain: str
    ) -> Dict[str, Any]:

        domain = self._normalize_domain(
            domain
        )

        if not domain:
            return {
                "status": "error",
                "source": "browser",
                "reason": "Invalid domain",
                "contacts": []
            }

        try:

            result = await self.browser_agent.find_contact_page(
                domain
            )

            if not isinstance(result, dict):
                return {
                    "status": "error",
                    "source": "browser",
                    "reason": (
                        "BrowserAgent returned invalid response"
                    ),
                    "contacts": []
                }

            contacts = result.get(
                "contacts",
                []
            ) or []

            emails = result.get(
                "emails",
                []
            ) or []

            linkedin_urls = result.get(
                "linkedin_urls",
                []
            ) or []

            found_url = result.get(
                "found_url"
            )

            pages_checked = result.get(
                "pages_checked",
                []
            ) or []

            normalized_contacts: List[Dict[str, Any]] = []

            # ------------------------------------------------
            # Normalize BrowserAgent contacts
            # ------------------------------------------------

            for contact in contacts:

                if not isinstance(contact, dict):
                    continue

                normalized_contacts.append({
                    "name": contact.get(
                        "name"
                    ),
                    "first_name": contact.get(
                        "first_name"
                    ),
                    "last_name": contact.get(
                        "last_name"
                    ),
                    "title": contact.get(
                        "title"
                    ),
                    "email": contact.get(
                        "email"
                    ),
                    "linkedin_url": (
                        contact.get(
                            "linkedin_url"
                        )
                        or contact.get(
                            "linkedin"
                        )
                    ),
                    "company": contact.get(
                        "company"
                    ),
                    "domain": domain,
                    "source": contact.get(
                        "source",
                        "browser"
                    ),
                    "source_url": contact.get(
                        "source_url"
                    ),
                    "confidence": contact.get(
                        "confidence",
                        "public"
                    )
                })

            # ------------------------------------------------
            # Convert BrowserAgent emails into contacts
            # ------------------------------------------------

            for email in emails:

                if not isinstance(email, str):
                    continue

                email = email.strip().lower()

                if not email or "@" not in email:
                    continue

                email_domain = email.split(
                    "@",
                    1
                )[1]

                if email_domain != domain:
                    continue

                name = self._name_from_email(
                    email
                )

                parts = name.split()

                normalized_contacts.append({
                    "name": name,
                    "first_name": (
                        parts[0]
                        if parts
                        else None
                    ),
                    "last_name": (
                        " ".join(parts[1:])
                        if len(parts) > 1
                        else None
                    ),
                    "title": None,
                    "email": email,
                    "linkedin_url": None,
                    "company": None,
                    "domain": domain,
                    "source": "browser",
                    "source_url": found_url,
                    "confidence": "public"
                })

            # ------------------------------------------------
            # Preserve LinkedIn candidates
            # ------------------------------------------------

            for linkedin_url in linkedin_urls:

                if not linkedin_url:
                    continue

                normalized_contacts.append({
                    "name": self._guess_name_from_linkedin(
                        linkedin_url
                    ),
                    "first_name": None,
                    "last_name": None,
                    "title": None,
                    "email": None,
                    "linkedin_url": linkedin_url,
                    "company": None,
                    "domain": domain,
                    "source": "browser",
                    "source_url": found_url,
                    "confidence": "public"
                })

            normalized_contacts = self._deduplicate_contacts(
                normalized_contacts
            )

            if normalized_contacts:
                return {
                    "status": "success",
                    "source": "browser",
                    "found_url": found_url,
                    "contacts": normalized_contacts[:20],
                    "emails": emails[:20],
                    "linkedin_urls": linkedin_urls[:20],
                    "pages_checked": pages_checked
                }

            return {
                "status": "not_found",
                "source": "browser",
                "found_url": found_url,
                "contacts": [],
                "emails": emails[:20],
                "linkedin_urls": linkedin_urls[:20],
                "pages_checked": pages_checked,
                "reason": result.get(
                    "reason",
                    "No public contacts found"
                )
            }

        except Exception as e:

            logger.exception(
                "Browser contact-page discovery failed for %s",
                domain
            )

            return {
                "status": "error",
                "source": "browser",
                "reason": str(e),
                "contacts": []
            }

    # ========================================================
    # LinkedIn Name Helper
    # ========================================================

    @staticmethod
    def _guess_name_from_linkedin(
        linkedin_url: str
    ) -> Optional[str]:

        if not linkedin_url:
            return None

        match = re.search(
            r"linkedin\.com/in/([^/?#]+)",
            linkedin_url,
            flags=re.IGNORECASE
        )

        if not match:
            return None

        slug = match.group(1)

        slug = re.sub(
            r"[-_]+",
            " ",
            slug
        )

        slug = re.sub(
            r"\d+$",
            "",
            slug
        ).strip()

        if not slug:
            return None

        return slug.title()

    # ========================================================
    # Clearbit
    # ========================================================

    async def enrich_company_clearbit(
        self,
        domain: str
    ) -> Dict[str, Any]:

        if not self.clearbit_key:
            return {
                "status": "skipped",
                "source": "clearbit",
                "reason": "CLEARBIT_API_KEY missing"
            }

        return {
            "status": "skipped",
            "source": "clearbit",
            "reason": "Clearbit integration pending"
        }

    # ========================================================
    # People Data Labs
    # ========================================================

    async def enrich_person_pdl(
        self,
        email: str
    ) -> Dict[str, Any]:

        if not self.pdl_key:
            return {
                "status": "skipped",
                "source": "pdl",
                "reason": "PDL_API_KEY missing"
            }

        return {
            "status": "skipped",
            "source": "pdl",
            "reason": "PDL integration pending"
        }

    # ========================================================
    # Provider Router - Company
    # ========================================================

    async def enrich_company(
        self,
        domain: str
    ) -> Dict[str, Any]:

        domain = self._normalize_domain(
            domain
        )

        if not domain:
            return {
                "status": "error",
                "reason": "Invalid or missing domain"
            }

        # ----------------------------------------------------
        # 1. Apollo
        # ----------------------------------------------------

        if self.apollo_key:

            apollo_result = await self.enrich_company_apollo(
                domain
            )

            if (
                apollo_result.get("status") == "success"
                and apollo_result.get("company")
            ):
                return apollo_result

            logger.warning(
                "Apollo company enrichment did not return "
                "usable data for %s. Falling back.",
                domain
            )

        # ----------------------------------------------------
        # 2. Clearbit
        # ----------------------------------------------------

        if self.clearbit_key:

            clearbit_result = await self.enrich_company_clearbit(
                domain
            )

            if (
                clearbit_result.get("status") == "success"
                and clearbit_result.get("company")
            ):
                return clearbit_result

            logger.warning(
                "Clearbit did not return usable data for %s. "
                "Falling back to BrowserAgent.",
                domain
            )

        # ----------------------------------------------------
        # 3. BrowserAgent
        # ----------------------------------------------------

        browser_result = await self.enrich_company_browser(
            domain
        )

        if (
            browser_result.get("status") == "success"
            and browser_result.get("company")
        ):
            return browser_result

        return {
            "status": "skipped",
            "domain": domain,
            "reason": (
                "No enrichment provider returned usable data"
            ),
            "browser": browser_result
        }

    # ========================================================
    # Lead Enrichment
    # ========================================================

    async def enrich_lead(
        self,
        domain: str
    ) -> Dict[str, Any]:

        domain = self._normalize_domain(
            domain
        )

        if not domain:
            return {
                "status": "error",
                "reason": "Invalid or missing domain",
                "contacts": [],
                "contacts_found": 0
            }

        # ----------------------------------------------------
        # Company enrichment
        # ----------------------------------------------------

        company = await self.enrich_company(
            domain
        )

        # ----------------------------------------------------
        # Contact enrichment
        # ----------------------------------------------------

        contacts: List[Dict[str, Any]] = []
        browser_contact = None

        # ----------------------------------------------------
        # 1. Apollo contacts - PRIMARY
        # ----------------------------------------------------

        if self.apollo_key:

            contacts = await self.find_contacts_apollo(
                domain
            )

            if contacts:
                logger.info(
                    "Apollo contact enrichment succeeded for %s",
                    domain
                )
            else:
                logger.info(
                    "Apollo contact search returned no usable "
                    "contacts for %s",
                    domain
                )

        # ----------------------------------------------------
        # 2. FREE public search fallback
        # ----------------------------------------------------

        if not contacts:

            logger.info(
                "Using free public search contact fallback "
                "for %s",
                domain
            )

            contacts = await self.find_contacts_search(
                domain
            )

        # ----------------------------------------------------
        # 3. Browser fallback
        # ----------------------------------------------------

        if not contacts:

            logger.info(
                "Free search found no contacts. "
                "Using BrowserAgent fallback for %s",
                domain
            )

            browser_contact = await self.find_contacts_browser(
                domain
            )

            contacts = browser_contact.get(
                "contacts",
                []
            ) or []

        # ----------------------------------------------------
        # Final deduplication
        # ----------------------------------------------------

        contacts = self._deduplicate_contacts(
            contacts
        )

        final_contacts = contacts[:20]

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        return {
            "status": "completed",
            "domain": domain,
            "company": company,
            "contacts": final_contacts,
            "contacts_found": len(final_contacts),
            "browser_contact": browser_contact
        }

    # ========================================================
    # Agent Entry Point
    # ========================================================

    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        context = context or {}

        domain = context.get(
            "domain"
        )

        email = context.get(
            "email"
        )

        company = (
            context.get("company_name")
            or context.get("company")
        )

        # ----------------------------------------------------
        # Determine domain from email
        # ----------------------------------------------------

        if (
            not domain
            and email
            and isinstance(email, str)
            and "@" in email
        ):

            domain = email.split(
                "@",
                1
            )[1].strip()

        # ----------------------------------------------------
        # Determine domain from company name
        # ----------------------------------------------------

        if not domain and company:

            company_clean = re.sub(
                r"[^a-zA-Z0-9]+",
                "",
                str(company).lower()
            )

            if company_clean:
                domain = f"{company_clean}.com"

        # ----------------------------------------------------
        # Normalize domain
        # ----------------------------------------------------

        domain = self._normalize_domain(
            domain
        )

        # ----------------------------------------------------
        # Validate domain
        # ----------------------------------------------------

        if not domain:

            logger.warning(
                "EnrichmentAgent could not determine domain. "
                "Task=%s Context=%s",
                task,
                context
            )

            return {
                "status": "error",
                "reason": "Unable to determine domain"
            }

        logger.info(
            "EnrichmentAgent starting enrichment for domain=%s",
            domain
        )

        # ----------------------------------------------------
        # Execute enrichment
        # ----------------------------------------------------

        return await self.enrich_lead(
            domain
        )