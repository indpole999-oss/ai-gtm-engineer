"""Allowlisted CRM reads; no invented atomic-write/idempotency guarantees."""
from urllib.parse import quote
from backend import providers


class CRMReadTransport:
    durable_idempotency = False
    atomic_versions = False
    objects = {"hubspot": {"company": "companies", "contact": "contacts", "opportunity": "deals"},
               "salesforce": {"company": "Account", "contact": "Contact", "opportunity": "Opportunity"}}

    def __init__(self, integration, credentials):
        self.integration, self.credentials = integration, credentials

    async def fetch(self, namespace, object_type, external_id):
        if namespace != str(self.integration.id):
            raise providers.ProviderError("integration_namespace_mismatch")
        kind = self.objects[self.integration.provider].get(object_type)
        if not kind or not external_id or len(external_id) > 255 or not external_id.isalnum():
            raise providers.ProviderError("invalid_crm_identity")
        token = self.credentials.get("access_token") or self.credentials.get("private_app_token") or self.credentials.get("api_key")
        if not token:
            raise providers.ProviderError("credential_required")
        if self.integration.provider == "hubspot":
            url = "https://api.hubapi.com/crm/v3/objects/" + kind + "/" + quote(external_id, safe="")
        else:
            url = providers.salesforce_origin(self.integration.config.get("instance_url")) + "/services/data/v61.0/sobjects/" + kind + "/" + quote(external_id, safe="")
        result = await providers.provider_request("GET", url, headers={"Authorization": "Bearer " + token})
        if str(result.get("id") or result.get("Id") or "") != external_id:
            raise providers.ProviderError("provider_identity_mismatch")
        return result

    async def lookup(self, *args):
        raise providers.ProviderError("crm_writes_disabled")

    async def apply(self, *args):
        # A read-then-write comparison is not atomic remote concurrency protection.
        raise providers.ProviderError("crm_atomic_writes_not_supported")
