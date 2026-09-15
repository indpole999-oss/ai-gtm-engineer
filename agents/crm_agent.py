"""
CRM Agent - Production CRM Integration

Supports:
- HubSpot
- Salesforce

Architecture:
- Customer-specific CRM credentials are loaded from the Integration table.
- Credentials are encrypted at rest and decrypted only when required.
- Every CRM lookup is scoped to the authenticated user_id.
- Workflow context is normalized from prospect/contact/enrichment/flat fields.

Expected workflow context:
{
    "user_id": "...",
    "company_name": "...",
    "domain": "...",
    "email": "...",
    "to_email": "...",
    "recipient_email": "...",
    "prospect": {...},
    "enrichment": {...}
}
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

import httpx
from sqlalchemy import select

from backend.database import Integration, AsyncSessionLocal
from backend.security import decrypt_credentials


logger = logging.getLogger(__name__)


# ============================================================
# LEGACY ENVIRONMENT FALLBACK
# ============================================================

CRM_PROVIDER = os.getenv(
    "CRM_PROVIDER",
    "hubspot",
).strip().lower()

HUBSPOT_API_KEY = os.getenv(
    "HUBSPOT_API_KEY",
    "",
).strip()

SALESFORCE_INSTANCE_URL = os.getenv(
    "SALESFORCE_INSTANCE_URL",
    "",
).strip().rstrip("/")

SALESFORCE_ACCESS_TOKEN = os.getenv(
    "SALESFORCE_ACCESS_TOKEN",
    "",
).strip()

HUBSPOT_API_BASE = "https://api.hubapi.com"


# ============================================================
# CRM AGENT
# ============================================================

class CRMAgent:
    """
    Production CRM agent.

    Primary credential source:
        integrations table

    Legacy fallback:
        environment variables

    The database integration always takes precedence when a
    connected user-owned integration exists.
    """

    def __init__(self):
        self.provider = CRM_PROVIDER

        # Legacy fallback only.
        self.hubspot_key = HUBSPOT_API_KEY
        self.sf_url = SALESFORCE_INSTANCE_URL
        self.sf_token = SALESFORCE_ACCESS_TOKEN

    # ========================================================
    # GENERAL HELPERS
    # ========================================================

    @staticmethod
    def _normalize_user_id(
        user_id: Any,
    ) -> Optional[UUID]:
        """
        Normalize authenticated user ID to UUID.

        Integration.user_id is a UUID column, so we explicitly
        normalize the incoming value before querying.
        """

        if not user_id:
            return None

        try:
            return UUID(str(user_id))
        except (
            ValueError,
            TypeError,
            AttributeError,
        ):
            logger.error(
                "CRM invalid user_id: %s",
                user_id,
            )
            return None

    @staticmethod
    def _safe_string(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _normalize_hubspot_industry(
        value: Any,
    ) -> str:
        """
        Normalize common free-form industry values into values
        accepted by HubSpot's enumerated industry property.

        HubSpot does not accept arbitrary text for the standard
        company industry field. For example:

            Artificial Intelligence -> COMPUTER_SOFTWARE
            AI                     -> COMPUTER_SOFTWARE
            Software               -> COMPUTER_SOFTWARE
            Computer Software      -> COMPUTER_SOFTWARE

        Unknown values are preserved so existing CRM behavior
        remains unchanged.
        """

        raw = str(
            value or ""
        ).strip()

        if not raw:
            return ""

        normalized = raw.lower()

        aliases = {
            "artificial intelligence":
                "COMPUTER_SOFTWARE",

            "ai":
                "COMPUTER_SOFTWARE",

            "software":
                "COMPUTER_SOFTWARE",

            "computer software":
                "COMPUTER_SOFTWARE",

            "software development":
                "COMPUTER_SOFTWARE",

            "information technology":
                "INFORMATION_TECHNOLOGY_AND_SERVICES",

            "information technology and services":
                "INFORMATION_TECHNOLOGY_AND_SERVICES",

            "internet":
                "INTERNET",
        }

        return aliases.get(
            normalized,
            raw,
        )

    # ========================================================
    # INTEGRATION LOOKUP
    # ========================================================

    async def _get_user_crm_integration(
        self,
        user_id: Any,
        provider: Optional[str] = None,
    ) -> Optional[Integration]:
        """
        Load a connected CRM integration belonging to the
        authenticated user.

        Security:
        The query is always scoped by user_id.
        """

        user_uuid = self._normalize_user_id(
            user_id
        )

        if not user_uuid:
            logger.error(
                "CRM integration lookup aborted: "
                "invalid user_id=%s",
                user_id,
            )
            return None

        provider_name = (
            self._safe_string(provider).lower()
            if provider
            else ""
        )

        try:
            async with AsyncSessionLocal() as session:

                query = select(Integration).where(
                    Integration.user_id == user_uuid,
                    Integration.category == "crm",
                    Integration.status == "connected",
                )

                if provider_name:
                    query = query.where(
                        Integration.provider
                        == provider_name
                    )

                query = query.order_by(
                    Integration.updated_at.desc()
                )

                result = await session.execute(
                    query
                )

                integration = (
                    result.scalars().first()
                )

                if not integration:
                    logger.info(
                        "CRM integration not found: "
                        "user_id=%s provider=%s",
                        user_uuid,
                        provider_name or "any",
                    )
                    return None

                logger.info(
                    "CRM integration found: "
                    "id=%s user_id=%s provider=%s",
                    integration.id,
                    integration.user_id,
                    integration.provider,
                )

                return integration

        except Exception:
            logger.exception(
                "CRM integration database lookup failed "
                "for user_id=%s",
                user_uuid,
            )
            return None

    async def _get_credentials(
        self,
        user_id: Any,
        provider: Optional[str] = None,
    ) -> tuple[
        Optional[str],
        Dict[str, Any],
        Optional[Integration],
    ]:
        """
        Return:

            provider
            decrypted credentials
            integration

        Database integration has priority.

        Environment variables are used only when no user-owned
        connected integration exists.
        """

        integration = (
            await self._get_user_crm_integration(
                user_id=user_id,
                provider=provider,
            )
        )

        if integration:

            try:
                credentials = decrypt_credentials(
                    integration.credentials
                )

            except Exception:
                logger.exception(
                    "CRM credentials could not be decrypted: "
                    "integration_id=%s",
                    integration.id,
                )

                return (
                    integration.provider,
                    {},
                    integration,
                )

            if not isinstance(
                credentials,
                dict,
            ):
                logger.error(
                    "CRM credentials are not a dictionary: "
                    "integration_id=%s",
                    integration.id,
                )

                return (
                    integration.provider,
                    {},
                    integration,
                )

            return (
                integration.provider.lower(),
                credentials,
                integration,
            )

        # ----------------------------------------------------
        # Legacy environment fallback
        # ----------------------------------------------------

        fallback_provider = (
            self._safe_string(provider).lower()
            if provider
            else self.provider
        )

        if (
            fallback_provider == "hubspot"
            and self.hubspot_key
        ):
            logger.warning(
                "Using legacy HUBSPOT_API_KEY fallback. "
                "User CRM integration was not found."
            )

            return (
                "hubspot",
                {
                    "access_token":
                        self.hubspot_key,
                    "api_key":
                        self.hubspot_key,
                },
                None,
            )

        if (
            fallback_provider == "salesforce"
            and self.sf_token
        ):
            logger.warning(
                "Using legacy Salesforce environment "
                "credentials. User CRM integration was "
                "not found."
            )

            return (
                "salesforce",
                {
                    "access_token":
                        self.sf_token,
                },
                None,
            )

        return (
            fallback_provider,
            {},
            None,
        )

    # ========================================================
    # CONTACT NORMALIZATION
    # ========================================================

    def _normalize_contact(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert the workflow's accumulated context into one
        consistent CRM contact object.

        Priority:
        1. context["contact"]
        2. context["prospect"]
        3. first contact from context["enrichment"]["contacts"]
        4. flat workflow fields
        """

        context = context or {}

        contact = context.get(
            "contact"
        )

        if not isinstance(
            contact,
            dict,
        ):
            contact = {}

        prospect = context.get(
            "prospect"
        )

        if not isinstance(
            prospect,
            dict,
        ):
            prospect = {}

        enrichment = context.get(
            "enrichment"
        )

        if not isinstance(
            enrichment,
            dict,
        ):
            enrichment = {}

        # ----------------------------------------------------
        # First discovered enrichment contact
        # ----------------------------------------------------

        enrichment_contact: Dict[
            str,
            Any,
        ] = {}

        contacts = enrichment.get(
            "contacts",
            [],
        )

        if (
            isinstance(contacts, list)
            and contacts
        ):
            if isinstance(
                contacts[0],
                dict,
            ):
                enrichment_contact = contacts[0]

        # ----------------------------------------------------
        # Merge with clear priority
        # ----------------------------------------------------

        merged: Dict[
            str,
            Any,
        ] = {}

        for source in (
            enrichment_contact,
            prospect,
            contact,
        ):
            if isinstance(
                source,
                dict,
            ):
                for key, value in source.items():
                    if value not in (
                        None,
                        "",
                        [],
                        {},
                    ):
                        merged[key] = value

        # ----------------------------------------------------
        # Flat workflow fields
        # ----------------------------------------------------

        company = (
            context.get("company_name")
            or context.get("company")
            or merged.get("company")
            or ""
        )

        domain = (
            context.get("domain")
            or merged.get("domain")
            or ""
        )

        email = (
            context.get("email")
            or context.get("to_email")
            or context.get("recipient_email")
            or context.get("recipient")
            or merged.get("email")
            or merged.get("email_address")
            or ""
        )

        first_name = (
            merged.get("first_name")
            or merged.get("firstname")
            or ""
        )

        last_name = (
            merged.get("last_name")
            or merged.get("lastname")
            or ""
        )

        full_name = (
            merged.get("name")
            or merged.get("full_name")
            or ""
        )

        # ----------------------------------------------------
        # Split full name when first/last are absent
        # ----------------------------------------------------

        if (
            full_name
            and not first_name
            and not last_name
        ):

            name_parts = (
                full_name.strip().split()
            )

            if len(name_parts) == 1:
                first_name = name_parts[0]

            elif len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = " ".join(
                    name_parts[1:]
                )

        title = (
            merged.get("title")
            or merged.get("job_title")
            or ""
        )

        linkedin_url = (
            merged.get("linkedin_url")
            or merged.get("linkedin")
            or ""
        )

        phone = (
            merged.get("phone")
            or merged.get("phone_number")
            or ""
        )

        return {
            "first_name": self._safe_string(
                first_name
            ),
            "last_name": self._safe_string(
                last_name
            ),
            "name": self._safe_string(
                full_name
            ),
            "email": self._safe_string(
                email
            ).lower(),
            "title": self._safe_string(
                title
            ),
            "company": self._safe_string(
                company
            ),
            "domain": self._safe_string(
                domain
            ).lower(),
            "linkedin_url": self._safe_string(
                linkedin_url
            ),
            "phone": self._safe_string(
                phone
            ),
        }

    # ========================================================
    # HUBSPOT GENERAL
    # ========================================================

    @staticmethod
    def _hubspot_headers(
        access_token: str,
    ) -> Dict[str, str]:
        return {
            "Authorization":
                f"Bearer {access_token}",
            "Content-Type":
                "application/json",
            "Accept":
                "application/json",
        }

    async def _hubspot_request(
        self,
        method: str,
        path: str,
        access_token: str,
        **kwargs,
    ) -> tuple[
        int,
        Dict[str, Any],
    ]:
        """
        Centralized HubSpot HTTP request handling.
        """

        url = (
            f"{HUBSPOT_API_BASE}"
            f"{path}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=30
            ) as client:

                response = await client.request(
                    method,
                    url,
                    headers=self._hubspot_headers(
                        access_token
                    ),
                    **kwargs,
                )

            try:
                data = response.json()
            except ValueError:
                data = {
                    "raw_text":
                        response.text
                }

            if not isinstance(
                data,
                dict,
            ):
                data = {
                    "data":
                        data
                }

            return (
                response.status_code,
                data,
            )

        except httpx.TimeoutException as exc:
            logger.error(
                "HubSpot request timed out: "
                "%s %s",
                method,
                path,
            )

            return (
                599,
                {
                    "error":
                        "HubSpot request timed out",
                    "detail":
                        str(exc),
                },
            )

        except httpx.HTTPError as exc:
            logger.error(
                "HubSpot HTTP request failed: %s",
                exc,
            )

            return (
                598,
                {
                    "error":
                        "HubSpot HTTP request failed",
                    "detail":
                        str(exc),
                },
            )

    async def test_hubspot_credentials(
        self,
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Verify a HubSpot token by querying the account's
        basic information endpoint.
        """

        access_token = (
            credentials.get(
                "access_token"
            )
            or credentials.get(
                "private_app_token"
            )
            or credentials.get(
                "api_key"
            )
        )

        if not access_token:
            return {
                "status":
                    "error",
                "reason":
                    "HubSpot access token is missing",
            }

        status_code, data = (
            await self._hubspot_request(
                "GET",
                "/account-info/v3/details",
                access_token,
            )
        )

        if 200 <= status_code < 300:
            return {
                "status":
                    "connected",
                "provider":
                    "hubspot",
                "account":
                    data,
            }

        return {
            "status":
                "error",
            "provider":
                "hubspot",
            "http_status":
                status_code,
            "reason": (
                data.get("message")
                or data.get("error")
                or "HubSpot authentication failed"
            ),
            "raw":
                data,
        }

    # ========================================================
    # HUBSPOT CONTACT
    # ========================================================

    async def search_contact_hubspot(
        self,
        email: str,
        access_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a HubSpot contact by exact email.
        """

        email = self._safe_string(
            email
        ).lower()

        if not email:
            return None

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return None

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName":
                                "email",
                            "operator":
                                "EQ",
                            "value":
                                email,
                        }
                    ]
                }
            ],
            "properties": [
                "firstname",
                "lastname",
                "email",
                "jobtitle",
                "company",
                "website",
                "phone",
            ],
            "limit": 1,
        }

        status_code, data = (
            await self._hubspot_request(
                "POST",
                "/crm/v3/objects/"
                "contacts/search",
                token,
                json=payload,
            )
        )

        if status_code != 200:
            logger.error(
                "HubSpot contact search failed: "
                "status=%s data=%s",
                status_code,
                data,
            )
            return None

        results = data.get(
            "results",
            [],
        )

        if results:
            return results[0]

        return None

    async def create_contact_hubspot(
        self,
        contact: Dict[str, Any],
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a HubSpot contact.
        """

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "HubSpot access token is missing",
            }

        email = self._safe_string(
            contact.get("email")
        ).lower()

        if not email:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "Contact email is required",
            }

        properties = {
            "firstname":
                contact.get(
                    "first_name",
                    "",
                ),
            "lastname":
                contact.get(
                    "last_name",
                    "",
                ),
            "email":
                email,
            "jobtitle":
                contact.get(
                    "title",
                    "",
                ),
            "company":
                contact.get(
                    "company",
                    "",
                ),
            "website":
                contact.get(
                    "domain",
                    "",
                ),
            "phone":
                contact.get(
                    "phone",
                    "",
                ),
        }

        payload = {
            "properties":
                properties
        }

        status_code, data = (
            await self._hubspot_request(
                "POST",
                "/crm/v3/objects/contacts",
                token,
                json=payload,
            )
        )

        if status_code == 201:
            return {
                "provider":
                    "hubspot",
                "contact_id":
                    data.get("id"),
                "status":
                    "created",
                "raw":
                    data,
            }

        return {
            "provider":
                "hubspot",
            "status":
                "failed",
            "http_status":
                status_code,
            "reason": (
                data.get("message")
                or data.get("error")
                or "HubSpot contact creation failed"
            ),
            "raw":
                data,
        }

    async def update_contact_hubspot(
        self,
        contact_id: str,
        contact: Dict[str, Any],
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing HubSpot contact.
        """

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "HubSpot access token is missing",
            }

        properties: Dict[
            str,
            Any,
        ] = {}

        mapping = {
            "first_name":
                "firstname",
            "last_name":
                "lastname",
            "email":
                "email",
            "title":
                "jobtitle",
            "company":
                "company",
            "domain":
                "website",
            "phone":
                "phone",
        }

        for (
            source_key,
            hubspot_key,
        ) in mapping.items():

            value = contact.get(
                source_key
            )

            if value not in (
                None,
                "",
            ):
                properties[
                    hubspot_key
                ] = value

        if not properties:
            return {
                "provider":
                    "hubspot",
                "contact_id":
                    contact_id,
                "status":
                    "unchanged",
            }

        status_code, data = (
            await self._hubspot_request(
                "PATCH",
                f"/crm/v3/objects/"
                f"contacts/{contact_id}",
                token,
                json={
                    "properties":
                        properties
                },
            )
        )

        if 200 <= status_code < 300:
            return {
                "provider":
                    "hubspot",
                "contact_id":
                    contact_id,
                "status":
                    "updated",
                "raw":
                    data,
            }

        return {
            "provider":
                "hubspot",
            "contact_id":
                contact_id,
            "status":
                "failed",
            "http_status":
                status_code,
            "reason": (
                data.get("message")
                or data.get("error")
                or "HubSpot contact update failed"
            ),
            "raw":
                data,
        }

    async def upsert_contact_hubspot(
        self,
        contact: Dict[str, Any],
        access_token: str,
    ) -> Dict[str, Any]:
        """
        Search first, then update existing contact or create
        a new one.
        """

        email = self._safe_string(
            contact.get("email")
        ).lower()

        if not email:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason": (
                    "A contact email is required "
                    "for HubSpot upsert."
                ),
            }

        existing = (
            await self.search_contact_hubspot(
                email=email,
                access_token=access_token,
            )
        )

        if existing:

            contact_id = existing.get(
                "id"
            )

            if not contact_id:
                return {
                    "provider":
                        "hubspot",
                    "status":
                        "failed",
                    "reason": (
                        "HubSpot returned an existing "
                        "contact without an ID."
                    ),
                }

            result = (
                await self.update_contact_hubspot(
                    contact_id=contact_id,
                    contact=contact,
                    access_token=access_token,
                )
            )

            result["operation"] = "upsert"
            result["existing"] = True

            return result

        result = (
            await self.create_contact_hubspot(
                contact=contact,
                access_token=access_token,
            )
        )

        result["operation"] = "upsert"
        result["existing"] = False

        return result

    # ========================================================
    # HUBSPOT COMPANY
    # ========================================================

    async def search_company_hubspot(
        self,
        domain: str,
        access_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a HubSpot company by exact domain.

        Domain is used as the duplicate-protection key.
        """

        domain = self._safe_string(
            domain
        ).lower()

        if not domain:
            return None

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return None

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName":
                                "domain",
                            "operator":
                                "EQ",
                            "value":
                                domain,
                        }
                    ]
                }
            ],
            "properties": [
                "name",
                "domain",
                "industry",
                "numberofemployees",
                "annualrevenue",
                "city",
                "description",
            ],
            "limit": 1,
        }

        status_code, data = (
            await self._hubspot_request(
                "POST",
                "/crm/v3/objects/"
                "companies/search",
                token,
                json=payload,
            )
        )

        if status_code != 200:
            logger.error(
                "HubSpot company search failed: "
                "status=%s data=%s",
                status_code,
                data,
            )
            return None

        results = data.get(
            "results",
            [],
        )

        if results:
            return results[0]

        return None

    async def create_company_hubspot(
        self,
        company: Dict[str, Any],
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a HubSpot company using standard properties.
        """

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "HubSpot access token is missing",
            }

        name = self._safe_string(
            company.get("name")
        )

        domain = self._safe_string(
            company.get("domain")
        ).lower()

        if not name:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "Company name is required",
            }

        properties: Dict[
            str,
            Any,
        ] = {
            "name":
                name,
        }

        if domain:
            properties[
                "domain"
            ] = domain

        mapping = {
            "industry":
                "industry",
            "employee_count":
                "numberofemployees",
            "revenue":
                "annualrevenue",
            "location":
                "city",
            "description":
                "description",
        }

        for (
            source_key,
            hubspot_key,
        ) in mapping.items():

            value = company.get(
                source_key
            )

            if source_key == "industry":
                value = (
                    self._normalize_hubspot_industry(
                        value
                    )
                )

            if value not in (
                None,
                "",
            ):
                properties[
                    hubspot_key
                ] = str(value)

        status_code, data = (
            await self._hubspot_request(
                "POST",
                "/crm/v3/objects/"
                "companies",
                token,
                json={
                    "properties":
                        properties
                },
            )
        )

        if status_code == 201:
            return {
                "provider":
                    "hubspot",
                "company_id":
                    data.get("id"),
                "status":
                    "created",
                "raw":
                    data,
            }

        return {
            "provider":
                "hubspot",
            "status":
                "failed",
            "http_status":
                status_code,
            "reason": (
                data.get("message")
                or data.get("error")
                or "HubSpot company creation failed"
            ),
            "raw":
                data,
        }

    async def update_company_hubspot(
        self,
        company_id: str,
        company: Dict[str, Any],
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing HubSpot company.
        """

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "HubSpot access token is missing",
            }

        properties: Dict[
            str,
            Any,
        ] = {}

        mapping = {
            "name":
                "name",
            "domain":
                "domain",
            "industry":
                "industry",
            "employee_count":
                "numberofemployees",
            "revenue":
                "annualrevenue",
            "location":
                "city",
            "description":
                "description",
        }

        for (
            source_key,
            hubspot_key,
        ) in mapping.items():

            value = company.get(
                source_key
            )

            if source_key == "industry":
                value = (
                    self._normalize_hubspot_industry(
                        value
                    )
                )

            if value not in (
                None,
                "",
            ):
                properties[
                    hubspot_key
                ] = str(value)

        if not properties:
            return {
                "provider":
                    "hubspot",
                "company_id":
                    company_id,
                "status":
                    "unchanged",
            }

        status_code, data = (
            await self._hubspot_request(
                "PATCH",
                f"/crm/v3/objects/"
                f"companies/{company_id}",
                token,
                json={
                    "properties":
                        properties
                },
            )
        )

        if 200 <= status_code < 300:
            return {
                "provider":
                    "hubspot",
                "company_id":
                    company_id,
                "status":
                    "updated",
                "raw":
                    data,
            }

        return {
            "provider":
                "hubspot",
            "company_id":
                company_id,
            "status":
                "failed",
            "http_status":
                status_code,
            "reason": (
                data.get("message")
                or data.get("error")
                or "HubSpot company update failed"
            ),
            "raw":
                data,
        }

    async def upsert_company_hubspot(
        self,
        company: Dict[str, Any],
        access_token: str,
    ) -> Dict[str, Any]:
        """
        Search by domain first.

        Existing company:
            update

        New company:
            create

        This prevents duplicate HubSpot companies when
        the domain matches.
        """

        domain = self._safe_string(
            company.get("domain")
        ).lower()

        if not domain:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason": (
                    "A company domain is required "
                    "for HubSpot company upsert."
                ),
            }

        existing = (
            await self.search_company_hubspot(
                domain=domain,
                access_token=access_token,
            )
        )

        if existing:

            company_id = existing.get(
                "id"
            )

            if not company_id:
                return {
                    "provider":
                        "hubspot",
                    "status":
                        "failed",
                    "reason": (
                        "HubSpot returned an existing "
                        "company without an ID."
                    ),
                }

            result = (
                await self.update_company_hubspot(
                    company_id=company_id,
                    company=company,
                    access_token=access_token,
                )
            )

            result["operation"] = "upsert"
            result["existing"] = True

            return result

        result = (
            await self.create_company_hubspot(
                company=company,
                access_token=access_token,
            )
        )

        result["operation"] = "upsert"
        result["existing"] = False

        return result

    # ========================================================
    # HUBSPOT ACTIVITY
    # ========================================================

    async def log_activity_hubspot(
        self,
        contact_id: str,
        note: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a HubSpot note associated with a contact.
        """

        token = (
            access_token
            or self.hubspot_key
        )

        if not token:
            return {
                "provider":
                    "hubspot",
                "status":
                    "error",
                "reason":
                    "HubSpot access token is missing",
            }

        note_text = self._safe_string(
            note
        )

        if not note_text:
            note_text = (
                "Activity logged by "
                "AI GTM Engineer."
            )

        payload = {
            "properties": {
                "hs_note_body":
                    note_text,
                "hs_timestamp": (
                    datetime.utcnow()
                    .isoformat()
                    + "Z"
                ),
            },
            "associations": [
                {
                    "to": {
                        "id":
                            contact_id
                    },
                    "types": [
                        {
                            "associationCategory":
                                "HUBSPOT_DEFINED",
                            "associationTypeId":
                                202,
                        }
                    ],
                }
            ],
        }

        status_code, data = (
            await self._hubspot_request(
                "POST",
                "/crm/v3/objects/notes",
                token,
                json=payload,
            )
        )

        if status_code == 201:
            return {
                "provider":
                    "hubspot",
                "note_id":
                    data.get("id"),
                "status":
                    "logged",
            }

        return {
            "provider":
                "hubspot",
            "status":
                "failed",
            "http_status":
                status_code,
            "reason": (
                data.get("message")
                or data.get("error")
                or "HubSpot activity logging failed"
            ),
            "raw":
                data,
        }

    # ========================================================
    # SALESFORCE
    # ========================================================

    @staticmethod
    def _salesforce_headers(
        access_token: str,
    ) -> Dict[str, str]:
        return {
            "Authorization":
                f"Bearer {access_token}",
            "Content-Type":
                "application/json",
            "Accept":
                "application/json",
        }

    async def create_lead_salesforce(
        self,
        contact: Dict[str, Any],
        access_token: Optional[str] = None,
        instance_url: Optional[str] = None,
    ) -> Dict[str, Any]:

        token = (
            access_token
            or self.sf_token
        )

        base_url = (
            instance_url
            or self.sf_url
        ).rstrip("/")

        if not token or not base_url:
            return {
                "provider":
                    "salesforce",
                "status":
                    "error",
                "reason": (
                    "Salesforce access token or "
                    "instance URL is missing"
                ),
            }

        company = (
            contact.get("company")
            or "Unknown"
        )

        last_name = (
            contact.get("last_name")
            or contact.get("name")
            or "Unknown"
        )

        payload = {
            "FirstName":
                contact.get(
                    "first_name",
                    "",
                ),
            "LastName":
                last_name,
            "Email":
                contact.get(
                    "email",
                    "",
                ),
            "Title":
                contact.get(
                    "title",
                    "",
                ),
            "Company":
                company,
            "Website":
                contact.get(
                    "domain",
                    "",
                ),
        }

        url = (
            f"{base_url}"
            "/services/data/v58.0/"
            "sobjects/Lead"
        )

        try:
            async with httpx.AsyncClient(
                timeout=30
            ) as client:

                response = await client.post(
                    url,
                    headers=self._salesforce_headers(
                        token
                    ),
                    json=payload,
                )

            try:
                data = response.json()
            except ValueError:
                data = {}

        except httpx.HTTPError as exc:
            return {
                "provider":
                    "salesforce",
                "status":
                    "error",
                "reason":
                    str(exc),
            }

        if (
            200 <= response.status_code < 300
            and data.get("success")
        ):
            return {
                "provider":
                    "salesforce",
                "lead_id":
                    data.get("id"),
                "status":
                    "created",
                "raw":
                    data,
            }

        return {
            "provider":
                "salesforce",
            "status":
                "failed",
            "http_status":
                response.status_code,
            "reason": (
                data.get("message")
                or data.get("errorCode")
                or "Salesforce lead creation failed"
            ),
            "raw":
                data,
        }

    async def log_task_salesforce(
        self,
        who_id: str,
        subject: str,
        description: str,
        access_token: Optional[str] = None,
        instance_url: Optional[str] = None,
    ) -> Dict[str, Any]:

        token = (
            access_token
            or self.sf_token
        )

        base_url = (
            instance_url
            or self.sf_url
        ).rstrip("/")

        if not token or not base_url:
            return {
                "provider":
                    "salesforce",
                "status":
                    "error",
                "reason": (
                    "Salesforce access token or "
                    "instance URL is missing"
                ),
            }

        payload = {
            "Subject":
                subject,
            "Description":
                description,
            "WhoId":
                who_id,
            "Status":
                "Completed",
            "ActivityDate":
                datetime.utcnow()
                .date()
                .isoformat(),
        }

        url = (
            f"{base_url}"
            "/services/data/v58.0/"
            "sobjects/Task"
        )

        try:
            async with httpx.AsyncClient(
                timeout=30
            ) as client:

                response = await client.post(
                    url,
                    headers=self._salesforce_headers(
                        token
                    ),
                    json=payload,
                )

            try:
                data = response.json()
            except ValueError:
                data = {}

        except httpx.HTTPError as exc:
            return {
                "provider":
                    "salesforce",
                "status":
                    "error",
                "reason":
                    str(exc),
            }

        if (
            200 <= response.status_code < 300
            and data.get("success")
        ):
            return {
                "provider":
                    "salesforce",
                "task_id":
                    data.get("id"),
                "status":
                    "created",
                "raw":
                    data,
            }

        return {
            "provider":
                "salesforce",
            "status":
                "failed",
            "http_status":
                response.status_code,
            "reason": (
                data.get("message")
                or data.get("errorCode")
                or "Salesforce task creation failed"
            ),
            "raw":
                data,
        }

    # ========================================================
    # PROVIDER DISPATCH - CONTACT
    # ========================================================

    async def upsert_contact(
        self,
        contact: Dict[str, Any],
        user_id: Any = None,
    ) -> Dict[str, Any]:
        """
        Upsert a contact using the authenticated user's CRM.
        """

        provider, credentials, integration = (
            await self._get_credentials(
                user_id=user_id
            )
        )

        if not credentials:
            return {
                "status":
                    "skipped",
                "reason":
                    "No CRM provider configured",
                "provider":
                    provider,
            }

        if provider == "hubspot":

            token = (
                credentials.get(
                    "access_token"
                )
                or credentials.get(
                    "private_app_token"
                )
                or credentials.get(
                    "api_key"
                )
            )

            if not token:
                return {
                    "provider":
                        "hubspot",
                    "status":
                        "error",
                    "reason": (
                        "Connected HubSpot integration "
                        "has no access token."
                    ),
                }

            result = (
                await self.upsert_contact_hubspot(
                    contact=contact,
                    access_token=token,
                )
            )

            if integration:
                result[
                    "integration_id"
                ] = str(
                    integration.id
                )

            return result

        if provider == "salesforce":

            token = credentials.get(
                "access_token"
            )

            instance_url = (
                credentials.get(
                    "instance_url"
                )
                or (
                    integration.config or {}
                ).get(
                    "instance_url"
                )
                if integration
                else None
            )

            result = (
                await self.create_lead_salesforce(
                    contact=contact,
                    access_token=token,
                    instance_url=instance_url,
                )
            )

            if integration:
                result[
                    "integration_id"
                ] = str(
                    integration.id
                )

            return result

        return {
            "status":
                "error",
            "provider":
                provider,
            "reason": (
                f"Unsupported CRM provider: "
                f"{provider}"
            ),
        }

    # ========================================================
    # PROVIDER DISPATCH - COMPANY
    # ========================================================

    async def upsert_company(
        self,
        company: Dict[str, Any],
        user_id: Any = None,
    ) -> Dict[str, Any]:
        """
        Upsert a company using the authenticated user's CRM.

        Currently:
            HubSpot

        Company duplicate protection:
            exact domain match
        """

        provider, credentials, integration = (
            await self._get_credentials(
                user_id=user_id
            )
        )

        if not credentials:
            return {
                "status":
                    "skipped",
                "reason":
                    "No CRM provider configured",
                "provider":
                    provider,
            }

        if provider == "hubspot":

            token = (
                credentials.get(
                    "access_token"
                )
                or credentials.get(
                    "private_app_token"
                )
                or credentials.get(
                    "api_key"
                )
            )

            if not token:
                return {
                    "provider":
                        "hubspot",
                    "status":
                        "error",
                    "reason": (
                        "Connected HubSpot integration "
                        "has no access token."
                    ),
                }

            result = (
                await self.upsert_company_hubspot(
                    company=company,
                    access_token=token,
                )
            )

            if integration:
                result[
                    "integration_id"
                ] = str(
                    integration.id
                )

            return result

        return {
            "status":
                "error",
            "provider":
                provider,
            "reason": (
                f"Company sync is not implemented "
                f"for CRM provider: {provider}"
            ),
        }

    # ========================================================
    # PROVIDER DISPATCH - ACTIVITY
    # ========================================================

    async def log_activity(
        self,
        record_id: str,
        note: str,
        user_id: Any = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log activity against an existing CRM record.
        """

        provider_name, credentials, integration = (
            await self._get_credentials(
                user_id=user_id,
                provider=provider,
            )
        )

        if not credentials:
            return {
                "status":
                    "skipped",
                "reason":
                    "No CRM provider configured",
                "provider":
                    provider_name,
            }

        if provider_name == "hubspot":

            token = (
                credentials.get(
                    "access_token"
                )
                or credentials.get(
                    "private_app_token"
                )
                or credentials.get(
                    "api_key"
                )
            )

            if not token:
                return {
                    "provider":
                        "hubspot",
                    "status":
                        "error",
                    "reason":
                        "HubSpot access token is missing",
                }

            result = (
                await self.log_activity_hubspot(
                    contact_id=record_id,
                    note=note,
                    access_token=token,
                )
            )

            if integration:
                result[
                    "integration_id"
                ] = str(
                    integration.id
                )

            return result

        if provider_name == "salesforce":

            token = credentials.get(
                "access_token"
            )

            instance_url = (
                credentials.get(
                    "instance_url"
                )
                or (
                    integration.config or {}
                ).get(
                    "instance_url"
                )
                if integration
                else None
            )

            result = (
                await self.log_task_salesforce(
                    who_id=record_id,
                    subject="GTM Agent Activity",
                    description=note,
                    access_token=token,
                    instance_url=instance_url,
                )
            )

            if integration:
                result[
                    "integration_id"
                ] = str(
                    integration.id
                )

            return result

        return {
            "status":
                "error",
            "provider":
                provider_name,
            "reason": (
                f"Unsupported CRM provider: "
                f"{provider_name}"
            ),
        }

    # ========================================================
    # MAIN ENTRY POINT
    # ========================================================

    async def run(
        self,
        task: str,
        context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Entry point called by ManagerAgent.

        Supports:
            upsert_contact
            upsert_company
            create
            create_contact
            add_lead
            update_contact
            outreach
            activity
            log_activity
            create_deal
            search_contact
        """

        context = context or {}

        action = context.get(
            "action",
            "upsert_contact",
        )

        # ----------------------------------------------------
        # Normalize workflow action names
        # ----------------------------------------------------

        action_mapping = {
            "create":
                "upsert_contact",
            "create_contact":
                "upsert_contact",
            "outreach":
                "full_intake",
            "add_lead":
                "upsert_contact",
            "update_contact":
                "upsert_contact",
            "activity":
                "log_activity",
        }

        action = action_mapping.get(
            action,
            action,
        )

        user_id = context.get(
            "user_id"
        )

        # ----------------------------------------------------
        # Normalize actual workflow contact
        # ----------------------------------------------------

        contact = self._normalize_contact(
            context
        )

        record_id = context.get(
            "record_id"
        )

        note = self._safe_string(
            context.get(
                "note",
                "",
            )
        )

        if not note:
            note = (
                "Lead processed by "
                "AI GTM Engineer. "
                f"Company: "
                f"{contact.get('company') or 'Unknown'}"
            )

        # ====================================================
        # UPSERT COMPANY
        # ====================================================

        if action == "upsert_company":

            company = context.get(
                "company",
                {},
            )

            if not isinstance(
                company,
                dict,
            ):
                company = {}

            return await self.upsert_company(
                company=company,
                user_id=user_id,
            )

        # ====================================================
        # UPSERT CONTACT
        # ====================================================

        if action == "upsert_contact":

            result = (
                await self.upsert_contact(
                    contact=contact,
                    user_id=user_id,
                )
            )

            return result

        # ====================================================
        # LOG ACTIVITY
        # ====================================================

        if action == "log_activity":

            if not record_id:
                return {
                    "status":
                        "error",
                    "reason": (
                        "record_id is required "
                        "for CRM activity logging."
                    ),
                }

            return await self.log_activity(
                record_id=record_id,
                note=note,
                user_id=user_id,
            )

        # ====================================================
        # FULL INTAKE
        # ====================================================

        if action == "full_intake":

            crm_result = (
                await self.upsert_contact(
                    contact=contact,
                    user_id=user_id,
                )
            )

            result_status = crm_result.get(
                "status"
            )

            record_id = (
                crm_result.get(
                    "contact_id"
                )
                or crm_result.get(
                    "lead_id"
                )
            )

            activity_result = None

            if (
                record_id
                and result_status in (
                    "created",
                    "updated",
                    "unchanged",
                )
            ):

                activity_result = (
                    await self.log_activity(
                        record_id=record_id,
                        note=note,
                        user_id=user_id,
                        provider=crm_result.get(
                            "provider"
                        ),
                    )
                )

            return {
                "status": (
                    "completed"
                    if result_status in (
                        "created",
                        "updated",
                        "unchanged",
                    )
                    else result_status
                ),
                "crm_result":
                    crm_result,
                "activity_result":
                    activity_result,
            }

        # ====================================================
        # SEARCH CONTACT
        # ====================================================

        if action == "search_contact":

            email = (
                context.get("email")
                or contact.get("email")
            )

            if not email:
                return {
                    "status":
                        "error",
                    "found":
                        False,
                    "reason": (
                        "Email is required for "
                        "CRM contact search."
                    ),
                }

            provider, credentials, integration = (
                await self._get_credentials(
                    user_id=user_id
                )
            )

            if provider == "hubspot":

                token = (
                    credentials.get(
                        "access_token"
                    )
                    or credentials.get(
                        "private_app_token"
                    )
                    or credentials.get(
                        "api_key"
                    )
                )

                if not token:
                    return {
                        "status":
                            "error",
                        "found":
                            False,
                        "provider":
                            "hubspot",
                        "reason": (
                            "HubSpot access token "
                            "is missing."
                        ),
                    }

                found = (
                    await self.search_contact_hubspot(
                        email=email,
                        access_token=token,
                    )
                )

                return {
                    "status":
                        "success",
                    "provider":
                        "hubspot",
                    "found":
                        found is not None,
                    "contact":
                        found,
                }

            return {
                "status":
                    "error",
                "found":
                    False,
                "provider":
                    provider,
                "reason": (
                    "Contact search is currently "
                    "implemented for HubSpot."
                ),
            }

        # ====================================================
        # CREATE DEAL
        # ====================================================

        if action == "create_deal":

            deal = context.get(
                "deal",
                {},
            )

            if not isinstance(
                deal,
                dict,
            ):
                deal = {}

            provider, credentials, integration = (
                await self._get_credentials(
                    user_id=user_id,
                    provider="hubspot",
                )
            )

            if provider != "hubspot":
                return {
                    "status":
                        "error",
                    "reason": (
                        "Deal creation currently "
                        "requires a HubSpot CRM "
                        "integration."
                    ),
                }

            token = (
                credentials.get(
                    "access_token"
                )
                or credentials.get(
                    "private_app_token"
                )
                or credentials.get(
                    "api_key"
                )
            )

            if not token:
                return {
                    "provider":
                        "hubspot",
                    "status":
                        "error",
                    "reason":
                        "HubSpot access token is missing.",
                }

            payload = {
                "properties": {
                    "dealname":
                        deal.get(
                            "name",
                            "",
                        ),
                    "dealstage":
                        deal.get(
                            "stage",
                            "appointmentscheduled",
                        ),
                    "pipeline":
                        deal.get(
                            "pipeline",
                            "default",
                        ),
                    "amount":
                        str(
                            deal.get(
                                "amount",
                                "",
                            )
                        ),
                    "closedate":
                        deal.get(
                            "close_date",
                            "",
                        ),
                }
            }

            if record_id:

                payload[
                    "associations"
                ] = [
                    {
                        "to": {
                            "id":
                                record_id
                        },
                        "types": [
                            {
                                "associationCategory":
                                    "HUBSPOT_DEFINED",
                                "associationTypeId":
                                    3,
                            }
                        ],
                    }
                ]

            status_code, data = (
                await self._hubspot_request(
                    "POST",
                    "/crm/v3/objects/deals",
                    token,
                    json=payload,
                )
            )

            if status_code == 201:
                return {
                    "provider":
                        "hubspot",
                    "deal_id":
                        data.get("id"),
                    "status":
                        "created",
                    "raw":
                        data,
                }

            return {
                "provider":
                    "hubspot",
                "status":
                    "failed",
                "http_status":
                    status_code,
                "reason": (
                    data.get("message")
                    or data.get("error")
                    or "HubSpot deal creation failed"
                ),
                "raw":
                    data,
            }

        # ====================================================
        # UNKNOWN ACTION
        # ====================================================

        return {
            "status":
                "error",
            "reason":
                f"Unknown action: {action}",
        }
