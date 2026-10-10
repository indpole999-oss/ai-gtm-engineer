"""Workspace-owned Resend transport. No HTTP route calls send.

Resend keys expire after 24h: an uncertain attempt is NEVER blindly resubmitted.
The worker persists intent before sending and exposes reconciliation on failure.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from email.utils import parseaddr
from sqlalchemy import select
from backend import providers, integration_service
from backend.config import settings
from backend.security import credentials_are_encrypted
from backend.outreach_service import address


class ResendTransport:
    durable_idempotency = False
    conservative_reconciliation = True

    def __init__(self, integration, credentials, message):
        self.integration, self.credentials, self.message = integration, credentials, message

    async def lookup(self, key):
        if self.message.attempted_at and not (self.message.error_code == "rate_limited" and
            datetime.utcnow() < self.message.attempted_at + timedelta(hours=23)):
            raise providers.ProviderError("delivery_reconciliation_required")
        return None

    async def send(self, key, envelope):
        # Recheck immediately at the external boundary; default is disconnected.
        if not settings.OUTBOUND_EMAIL_ENABLED:
            raise providers.ProviderError("outbound_email_paused")
        if address(envelope["sender"]) != address(self.integration.config.get("from_email")):
            raise providers.ProviderError("sender_identity_mismatch")
        result = await providers.provider_request("POST", "https://api.resend.com/emails",
            headers={"Authorization": "Bearer " + (self.credentials.get("api_key") or self.credentials["access_token"]), "Idempotency-Key": key},
            json={"from": envelope["sender"], "to": [envelope["recipient"]],
                  "subject": envelope["subject"], "text": envelope["body"],
                  "tags": [{"name": "gaps_message", "value": key.rsplit(":", 1)[1]}]})
        try:
            provider_id = str(UUID(result["id"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise providers.ProviderError("invalid_delivery_receipt")
        return {"status": "accepted", "id": provider_id}


async def for_sender(db, sender, message):
    if not settings.OUTBOUND_EMAIL_ENABLED:
        raise providers.ProviderError("outbound_email_paused")
    row = await integration_service.connection(db, sender.integration_id, lock=True)
    if (row.category, row.provider) != ("email", "resend") or row.status != "connected" or row.health != "healthy" or row.reconnect_required:
        raise providers.ProviderError("sender_connection_unavailable")
    if not credentials_are_encrypted(row.credentials):
        raise providers.ProviderError("encrypted_credentials_required")
    credentials = await integration_service.refresh_if_needed(db, row, row.user_id)
    if not (credentials.get("api_key") or credentials.get("access_token")):
        raise providers.ProviderError("credential_required")
    return ResendTransport(row, credentials, message)


async def reconcile_receipt(db, sender, data):
    """Authenticate via provider GET first. This records facts; it never sends."""
    from backend.outreach_models import Message, MessageDraft, DeliveryEvent
    from backend.research_service import scoped_record
    from backend.outreach_service import lock_workspace
    from backend.planning_models import ExecutionCycle
    from backend.planning_service import digest
    from backend import pipeline_service
    from fastapi import HTTPException
    tags = {t["name"]: t["value"] for t in data.get("tags", [])}
    try:
        message_id = UUID(tags["gaps_message"])
        accepted = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
        provider_id = str(UUID(data["id"]))
    except (ValueError, KeyError, TypeError):
        raise providers.ProviderError("delivery_receipt_identity_missing") from None
    await lock_workspace(db)
    message = await scoped_record(db, Message, message_id)
    draft = await scoped_record(db, MessageDraft, message.draft_id)
    envelope = draft.envelope
    if (not message.attempted_at or accepted < message.attempted_at - timedelta(minutes=5) or
        message.approved_hash != digest(envelope) or envelope["sender_id"] != str(sender.id) or
        address(parseaddr(data.get("from", ""))[1]) != envelope["sender"] or data.get("to") != [envelope["recipient"]] or
        data.get("subject") != envelope["subject"] or data.get("text") != envelope["body"] or
        data.get("cc") or data.get("bcc") or data.get("scheduled_at")):
        raise HTTPException(409, "Provider receipt does not match the approved attempted message")
    if message.state == "sent" and message.provider_message_id != provider_id:
        raise HTTPException(409, "Provider receipt conflicts with existing acceptance")
    if await db.scalar(select(Message.id).where(Message.provider_message_id == provider_id, Message.id != message.id)):
        raise HTTPException(409, "Provider identity already belongs to another message")
    key = f"{message.workspace_id}:{message.id}:accepted"
    if not await db.scalar(select(DeliveryEvent.id).where(DeliveryEvent.provider_event_id == key)):
        message.state, message.provider_message_id, message.accepted_at, message.error_code = "sent", provider_id, accepted, None
        db.add(DeliveryEvent(message_id=message.id, provider_event_id=key, kind="accepted"))
        cycle = await db.scalar(select(ExecutionCycle).where(ExecutionCycle.plan_id == message.plan_id))
        if not cycle:
            raise HTTPException(409, "Approved delivery execution missing")
        await pipeline_service.outbound(db, message, draft, cycle)
    rfc_id = data.get("message_id")
    if isinstance(rfc_id, str) and rfc_id:
        alias = "rfc:" + str(sender.id) + ":" + digest(rfc_id)
        existing = await db.scalar(select(DeliveryEvent).where(DeliveryEvent.provider_event_id == alias))
        if existing and existing.message_id != message.id:
            raise HTTPException(409, "RFC message identity conflict")
        if not existing:
            db.add(DeliveryEvent(message_id=message.id, provider_event_id=alias, kind="rfc_message_id"))
    await db.commit()
    return message
