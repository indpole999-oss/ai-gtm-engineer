"""Provider contracts. No deployment-global customer credentials or arbitrary URLs."""
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Protocol
import httpx
from pydantic import BaseModel, ConfigDict, Field
from backend.config import settings


class ProviderError(Exception):
    """Safe public code only; never include a response body or credentials."""
    def __init__(self, code="provider_unavailable"):
        self.code = code
        super().__init__(code)


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = "healthy"
    scopes: list[str] = Field(default_factory=list)


class ProviderAdapter(Protocol):
    async def verify(self, credentials: dict, config: dict) -> ProviderHealth: ...


@dataclass(frozen=True)
class ProviderContract:
    category: str
    provider: str
    auth_types: tuple[str, ...]
    config_keys: tuple[str, ...] = ()


CONTRACTS = {
    ("calendar", "google"): ProviderContract("calendar", "google", ("oauth2",), ("calendar_id",)),
    ("crm", "hubspot"): ProviderContract("crm", "hubspot", ("oauth2", "api_key", "bearer")),
    ("crm", "salesforce"): ProviderContract("crm", "salesforce", ("oauth2", "bearer"), ("instance_url",)),
    ("email", "gmail"): ProviderContract("email", "gmail", ("oauth2",)),
    ("email", "outlook"): ProviderContract("email", "outlook", ("oauth2",)),
    ("email", "resend"): ProviderContract("email", "resend", ("api_key", "bearer"), ("from_email",)),
    ("search", "serper"): ProviderContract("search", "serper", ("api_key",)),
    ("enrichment", "apollo"): ProviderContract("enrichment", "apollo", ("api_key",)),
}


def salesforce_origin(value):
    parsed = urlparse(value or "")
    if (parsed.scheme != "https" or not parsed.hostname or
        not parsed.hostname.endswith(".my.salesforce.com") or parsed.username or
        parsed.password or parsed.port not in (None, 443) or parsed.path not in ("", "/") or
        parsed.query or parsed.fragment):
        raise ProviderError("invalid_salesforce_instance")
    return f"https://{parsed.hostname}"


def validate_connection(category, provider, auth_type, credentials, config):
    contract = CONTRACTS.get((category, provider))
    if not contract or auth_type not in contract.auth_types:
        raise ProviderError("unsupported_connection_contract")
    if set(config) - set(contract.config_keys):
        raise ProviderError("unsupported_configuration_field")
    if not any(isinstance(credentials.get(key), str) and credentials[key].strip()
               for key in ("access_token", "api_key", "private_app_token")):
        raise ProviderError("credential_required")
    if provider == "salesforce":
        salesforce_origin(config.get("instance_url"))
    return contract


async def provider_request(method, url, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.request(method, url, **kwargs)
        if response.status_code in (401, 403):
            raise ProviderError("reconnect_required")
        if response.status_code == 429:
            raise ProviderError("rate_limited")
        if not 200 <= response.status_code < 300:
            raise ProviderError()
        return response.json() if response.content else {}
    except (httpx.HTTPError, ValueError):
        raise ProviderError() from None


class HttpProvider:
    def __init__(self, category, provider):
        self.category, self.provider = category, provider

    async def verify(self, credentials, config):
        token = credentials.get("access_token") or credentials.get("api_key") or credentials.get("private_app_token")
        if not token:
            raise ProviderError("credential_required")
        headers = {"Authorization": f"Bearer {token}"}
        endpoints = {
            "google": "https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1",
            "hubspot": "https://api.hubapi.com/account-info/v3/details",
            "gmail": "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            "outlook": "https://graph.microsoft.com/v1.0/me?$select=id",
            "resend": "https://api.resend.com/domains",
            "apollo": "https://api.apollo.io/api/v1/auth/health",
        }
        if self.provider == "salesforce":
            endpoint = salesforce_origin(config.get("instance_url")) + "/services/data/v61.0/limits"
        elif self.provider == "serper":
            # Serper has no non-billable identity endpoint. Do not spend search
            # credits merely to mark a connection healthy.
            return ProviderHealth(status="configured_unverified")
        else:
            endpoint = endpoints[self.provider]
        if self.provider == "apollo":
            headers = {"X-Api-Key": token}
        await provider_request("GET", endpoint, headers=headers)
        return ProviderHealth(scopes=credentials.get("scopes", []))


def get_provider(category, provider) -> ProviderAdapter:
    if (category, provider) not in CONTRACTS:
        raise ProviderError("unsupported_connection_contract")
    return HttpProvider(category, provider)


class GoogleOAuth:
    async def exchange(self, code, verifier):
        return await provider_request("POST", "https://oauth2.googleapis.com/token", data={
            "code":code, "code_verifier":verifier, "client_id":settings.GOOGLE_CLIENT_ID,
            "client_secret":settings.GOOGLE_CLIENT_SECRET, "redirect_uri":settings.GOOGLE_REDIRECT_URI,
            "grant_type":"authorization_code"})

    async def refresh(self, refresh_token):
        return await provider_request("POST", "https://oauth2.googleapis.com/token", data={
            "refresh_token":refresh_token, "client_id":settings.GOOGLE_CLIENT_ID,
            "client_secret":settings.GOOGLE_CLIENT_SECRET, "grant_type":"refresh_token"})

    async def revoke(self, token):
        return await provider_request("POST", "https://oauth2.googleapis.com/revoke", data={"token":token})
