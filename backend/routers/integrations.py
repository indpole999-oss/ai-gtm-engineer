from backend.tenancy import get_workspace_db as get_db
"""
Integration Router

Production-ready per-user integrations.

Supports:
- Google Calendar OAuth2
- HubSpot CRM
- Salesforce CRM
- Encrypted credentials
- Per-user isolation
- Real provider credential validation
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import Integration
from backend.routers.auth import get_current_user
from backend.security import encrypt_credentials, decrypt_credentials


try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    Credentials = None
    build = None


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/integrations",
    tags=["Integrations"],
)


# ============================================================
# SCHEMAS
# ============================================================

class IntegrationCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(..., min_length=1, max_length=100)
    auth_type: str = Field(default="api_key", max_length=50)
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=50)
    provider: Optional[str] = Field(default=None, max_length=100)
    auth_type: Optional[str] = Field(default=None, max_length=50)
    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(default=None, max_length=50)


# ============================================================
# HELPERS
# ============================================================

def integration_response(integration: Integration) -> Dict[str, Any]:
    """
    Never expose encrypted/decrypted credentials.
    """

    return {
        "id": str(integration.id),
        "user_id": str(integration.user_id),
        "category": integration.category,
        "provider": integration.provider,
        "auth_type": integration.auth_type,
        "config": {key: value for key, value in (integration.config or {}).items() if key in {"calendar_id", "instance_url", "api_version"}},
        "status": integration.status,
        "last_connected_at": (
            integration.last_connected_at.isoformat()
            if integration.last_connected_at
            else None
        ),
        "last_error": "Provider connection failed" if integration.last_error else None,
        "created_at": (
            integration.created_at.isoformat()
            if integration.created_at
            else None
        ),
        "updated_at": (
            integration.updated_at.isoformat()
            if integration.updated_at
            else None
        ),
    }


async def get_user_integration(
    integration_id: UUID,
    current_user,
    db: AsyncSession,
) -> Integration:
    """
    Retrieve an integration belonging to the authenticated user.
    """

    # Both database columns are UUID types.
    # Explicit conversion prevents SQLAlchemy UUID binding errors.
    integration_uuid = UUID(str(integration_id))
    user_uuid = UUID(str(current_user.id))

    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_uuid,
            Integration.workspace_id == db.info["workspace_id"],
        )
    )

    integration = result.scalars().first()

    if not integration:
        raise HTTPException(
            status_code=404,
            detail="Integration not found",
        )

    return integration


# ============================================================
# LIST INTEGRATIONS
# ============================================================

@router.get("")
async def list_integrations(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = UUID(str(current_user.id))

    result = await db.execute(
        select(Integration)
        .where(Integration.workspace_id == db.info["workspace_id"])
        .order_by(Integration.updated_at.desc())
    )

    integrations = result.scalars().all()

    return {
        "status": "success",
        "integrations": [
            integration_response(item)
            for item in integrations
        ],
    }


# ============================================================
# GET SINGLE INTEGRATION
# ============================================================

@router.get("/{integration_id}")
async def get_integration(
    integration_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    integration = await get_user_integration(
        integration_id,
        current_user,
        db,
    )

    return integration_response(integration)


# ============================================================
# CREATE INTEGRATION
# ============================================================

@router.post("")
async def create_integration(
    payload: IntegrationCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = UUID(str(current_user.id))

    encrypted_credentials = encrypt_credentials(
        payload.credentials or {}
    )

    integration = Integration(
        user_id=user_uuid,
        category=payload.category.lower().strip(),
        provider=payload.provider.lower().strip(),
        auth_type=payload.auth_type.lower().strip(),
        credentials=encrypted_credentials,
        config=payload.config or {},
        status="disconnected",
        last_error=None,
    )

    db.add(integration)

    await db.commit()
    await db.refresh(integration)

    return integration_response(integration)


# ============================================================
# UPDATE INTEGRATION
# ============================================================

@router.put("/{integration_id}")
async def update_integration(
    integration_id: UUID,
    payload: IntegrationUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    integration = await get_user_integration(
        integration_id,
        current_user,
        db,
    )

    if payload.category is not None:
        integration.category = payload.category.lower().strip()

    if payload.provider is not None:
        integration.provider = payload.provider.lower().strip()

    if payload.auth_type is not None:
        integration.auth_type = payload.auth_type.lower().strip()

    if payload.credentials is not None:
        integration.credentials = encrypt_credentials(
            payload.credentials
        )

    if payload.config is not None:
        integration.config = payload.config

    if payload.status is not None:
        integration.status = payload.status

    integration.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(integration)

    return integration_response(integration)


# ============================================================
# DELETE INTEGRATION
# ============================================================

@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    integration = await get_user_integration(
        integration_id,
        current_user,
        db,
    )

    await db.delete(integration)
    await db.commit()

    return {
        "status": "success",
        "message": "Integration deleted",
    }


# ============================================================
# GOOGLE CALENDAR TEST
# ============================================================

async def test_google_calendar(
    integration: Integration,
    credentials: Dict[str, Any],
) -> Dict[str, Any]:

    if Credentials is None or build is None:
        raise RuntimeError(
            "Google Calendar dependencies are not installed"
        )

    access_token = credentials.get("access_token")
    refresh_token = credentials.get("refresh_token")

    if not access_token and not refresh_token:
        raise ValueError(
            "Google Calendar credentials are missing "
            "access_token and refresh_token"
        )

    from backend.config import settings

    google_credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=credentials.get(
            "token_uri",
            "https://oauth2.googleapis.com/token",
        ),
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=credentials.get("scopes"),
    )

    if (
        google_credentials.expired
        and google_credentials.refresh_token
    ):
        from google.auth.transport.requests import Request

        google_credentials.refresh(Request())

        credentials["access_token"] = google_credentials.token

        integration.credentials = encrypt_credentials(
            credentials
        )

    service = build(
        "calendar",
        "v3",
        credentials=google_credentials,
        cache_discovery=False,
    )

    calendar_list = (
        service.calendarList()
        .list(maxResults=1)
        .execute()
    )

    calendars = calendar_list.get("items", [])

    return {
        "provider": "google",
        "status": "connected",
        "calendars_found": len(calendars),
    }


# ============================================================
# HUBSPOT TEST
# ============================================================

async def test_hubspot(
    credentials: Dict[str, Any],
) -> Dict[str, Any]:

    token = (
        credentials.get("access_token")
        or credentials.get("private_app_token")
        or credentials.get("api_key")
    )

    if not token:
        raise ValueError(
            "HubSpot credentials are missing. "
            "Provide access_token, private_app_token, or api_key."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    url = "https://api.hubapi.com/account-info/v3/details"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url,
            headers=headers,
        )

    if response.status_code == 200:
        data = response.json()

        return {
            "provider": "hubspot",
            "status": "connected",
            "portal_id": data.get("portalId"),
            "hub_domain": data.get("hubDomain"),
        }

    if response.status_code in (401, 403):
        raise ValueError(
            "HubSpot authentication failed. "
            "Check the access token/private app token."
        )

    try:
        error_data = response.json()

        error_message = (
            error_data.get("message")
            or error_data.get("error")
            or response.text
        )

    except Exception:
        error_message = response.text

    raise ValueError(
        f"HubSpot API validation failed "
        f"(HTTP {response.status_code}): "
        f"{error_message[:500]}"
    )


# ============================================================
# SALESFORCE TEST
# ============================================================

async def test_salesforce(
    credentials: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:

    access_token = credentials.get("access_token")

    instance_url = (
        credentials.get("instance_url")
        or (config or {}).get("instance_url")
    )

    if not access_token:
        raise ValueError(
            "Salesforce access_token is missing"
        )

    if not instance_url:
        raise ValueError(
            "Salesforce instance_url is missing"
        )

    instance_url = instance_url.rstrip("/")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    url = (
        f"{instance_url}"
        "/services/data/v58.0/limits"
    )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url,
            headers=headers,
        )

    if response.status_code == 200:
        return {
            "provider": "salesforce",
            "status": "connected",
        }

    if response.status_code in (401, 403):
        raise ValueError(
            "Salesforce authentication failed."
        )

    raise ValueError(
        f"Salesforce API validation failed "
        f"(HTTP {response.status_code}): "
        f"{response.text[:500]}"
    )


# ============================================================
# TEST INTEGRATION
# ============================================================

@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    integration = await get_user_integration(
        integration_id,
        current_user,
        db,
    )

    try:
        credentials = decrypt_credentials(
            integration.credentials or {}
        )

        provider = (
            integration.provider or ""
        ).lower().strip()

        category = (
            integration.category or ""
        ).lower().strip()

        # ----------------------------------------------------
        # GOOGLE CALENDAR
        # ----------------------------------------------------

        if (
            category == "calendar"
            and provider == "google"
        ):
            result = await test_google_calendar(
                integration,
                credentials,
            )

        # ----------------------------------------------------
        # HUBSPOT CRM
        # ----------------------------------------------------

        elif (
            category == "crm"
            and provider == "hubspot"
        ):
            result = await test_hubspot(
                credentials
            )

        # ----------------------------------------------------
        # SALESFORCE CRM
        # ----------------------------------------------------

        elif (
            category == "crm"
            and provider == "salesforce"
        ):
            result = await test_salesforce(
                credentials,
                integration.config or {},
            )

        # ----------------------------------------------------
        # UNSUPPORTED PROVIDER
        # ----------------------------------------------------

        else:
            raise ValueError(
                f"No real connection test implemented for "
                f"category='{category}', "
                f"provider='{provider}'"
            )

        integration.status = "connected"
        integration.last_connected_at = datetime.utcnow()
        integration.last_error = None
        integration.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(integration)

        return {
            "status": "success",
            "message": (
                f"{provider.title()} connection "
                "verified successfully"
            ),
            "integration": integration_response(
                integration
            ),
            "test_result": result,
        }

    except Exception as exc:

        logger.exception(
            "Integration test failed: %s",
            exc,
        )

        integration.status = "error"
        integration.last_error = str(exc)[:2000]
        integration.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(integration)

        return {
            "status": "error",
            "message": (
                f"{integration.provider.title()} "
                "connection test failed"
            ),
            "error": str(exc),
            "integration": integration_response(
                integration
            ),
        }