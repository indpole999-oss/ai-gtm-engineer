"""Provider boundary for durable outcomes; live mutations are deliberately disabled.

A transport must support authoritative operation lookup, stable create identities,
and atomic expected-version writes. A read-then-write check is NOT sufficient.
Tests inject a separate durable provider ledger. No HTTP client is constructed here.
"""
from typing import Protocol
from backend.providers import ProviderError


class OutcomeTransport(Protocol):
    durable_idempotency: bool
    atomic_versions: bool
    async def lookup(self, namespace, key): ...
    async def fetch(self, namespace, object_type, external_id): ...
    async def apply(self, namespace, key, request): ...


class DisabledTransport:
    durable_idempotency = False
    atomic_versions = False
    async def lookup(self, *args):
        raise ProviderError("live_outcomes_disabled")
    async def fetch(self, *args):
        raise ProviderError("live_outcomes_disabled")
    async def apply(self, *args):
        raise ProviderError("live_outcomes_disabled")


def transport_for(integration, credentials):
    return DisabledTransport()


class HubSpotAdapter:
    objects = {"company": "companies", "contact": "contacts", "opportunity": "deals"}
    def __init__(self, transport):
        self.transport = transport
    def encode(self, payload):
        kind = payload["object_type"]
        return {"object_type": self.objects[kind], "properties": payload["properties"],
            "external_id": payload["external_id"], "expected_version": payload["remote_version"],
            "local_key": payload["local_key"]}


class SalesforceAdapter(HubSpotAdapter):
    def encode(self, payload):
        raise ProviderError("salesforce_writes_not_implemented")


class GoogleCalendarAdapter(HubSpotAdapter):
    def encode(self, payload):
        return {"object_type": "events", "external_id": payload["event_id"], "expected_version": None,
            "local_key": payload["duplicate_key"], "properties": {
                "calendar_id": payload["calendar_id"], "summary": payload["title"],
                "attendees": [{"email": e} for e in payload["attendees"]],
                "start": {"dateTime": payload["start"], "timeZone": payload["timezone"]},
                "end": {"dateTime": payload["end"], "timeZone": payload["timezone"]},
                "id": payload["event_id"]}}


def adapter_for(integration, credentials):
    transport = transport_for(integration, credentials)
    classes = {("crm", "hubspot"): HubSpotAdapter, ("crm", "salesforce"): SalesforceAdapter, ("calendar", "google"): GoogleCalendarAdapter}
    adapter = classes.get((integration.category, integration.provider))
    if not adapter:
        raise ProviderError("unsupported_outcome_provider")
    return adapter(transport)
