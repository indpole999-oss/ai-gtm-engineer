"""Resend's signed webhook is a narrow workspace/mailbox capability, not login."""
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from email.utils import parseaddr
from uuid import UUID
from html.parser import HTMLParser
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from backend.config import settings
from backend.database import get_db, Workspace
from backend.outreach_models import SenderIdentity
from backend.security import decrypt_credentials, credentials_are_encrypted
from backend import providers, integration_service, inbox_service, outreach_service

router = APIRouter(prefix="/mailbox-webhooks", tags=["Trusted mailbox ingestion"])


def verify_signature(raw, headers, secret):
    """Svix v1: sign exact raw bytes with bounded timestamp and rotated signatures."""
    try:
        event_id, timestamp = headers["svix-id"], headers["svix-timestamp"]
        if not 1 <= len(event_id) <= 255 or abs(time.time() - int(timestamp)) > 300:
            raise ValueError()
        if not secret.startswith("whsec_"):
            raise ValueError()
        key = base64.b64decode(secret[6:], validate=True)
        if len(key) < 16:
            raise ValueError()
        expected = base64.b64encode(hmac.new(key, event_id.encode() + b"." + timestamp.encode() + b"." + raw, hashlib.sha256).digest()).decode()
        if not any(hmac.compare_digest(part[3:], expected) for part in headers["svix-signature"].split() if part.startswith("v1,")):
            raise ValueError()
        return event_id
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, "Invalid provider signature") from None


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}: self.hidden += 1
        elif tag in {"p", "div", "br", "li"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style"}: self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def inbound_event(data, event_id, sender):
    if [outreach_service.address(parseaddr(value)[1]) for value in data.get("to", [])] != [sender.email]:
        raise HTTPException(409, "Received email does not match the authenticated mailbox")
    body = data.get("text")
    if not body and isinstance(data.get("html"), str):
        parser = TextOnly()
        parser.feed(data["html"])
        body = "".join(parser.parts).strip()
    headers = {k.lower(): v for k, v in (data.get("headers") or {}).items()}
    auto = headers.get("auto-submitted", "no").lower()
    # Provider-authenticated delivery does not prove a correspondent's identity.
    # RFC reply headers are preserved only when the receiving provider verifies DMARC.
    reply = headers.get("in-reply-to") if (data.get("authentication") or {}).get("dmarc") == "pass" else None
    return inbox_service.InboundEvent(provider_event_id=event_id, provider_message_id=data["id"],
        sender_email=parseaddr(data["from"])[1], recipient_email=sender.email,
        subject=data.get("subject", ""), body=body or "", in_reply_to=reply,
        auto_submitted=auto if auto in {"auto-replied", "auto-generated"} else "no",
        received_at=data.get("created_at"))


@router.post("/resend/{workspace_id}/{integration_id}/{sender_id}", status_code=202)
async def resend_webhook(workspace_id: UUID, integration_id: UUID, sender_id: UUID,
                         request: Request, db=Depends(get_db)):
    if not settings.MAILBOX_INGESTION_ENABLED:
        raise HTTPException(503, "Mailbox ingestion is paused")
    # Stream limit applies even without a trustworthy Content-Length header.
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1048576:
            raise HTTPException(413, "Provider event too large")
    db.info.update(workspace_id=workspace_id, workspace_role="owner")
    workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id, Workspace.status == "active"))
    if not workspace:
        raise HTTPException(404, "Mailbox unavailable")
    integration = await integration_service.connection(db, integration_id, lock=True)
    if ((integration.category, integration.provider) != ("email", "resend") or
        integration.status != "connected" or integration.health != "healthy" or integration.reconnect_required or
        not credentials_are_encrypted(integration.credentials)):
        raise HTTPException(409, "Mailbox connection unavailable")
    credentials = decrypt_credentials(integration.credentials)
    event_id = verify_signature(bytes(raw), request.headers, credentials.get("webhook_secret", ""))
    from backend.research_service import scoped_record
    sender = await scoped_record(db, SenderIdentity, sender_id)
    if sender.provider != "resend" or sender.integration_id != integration.id or sender.status != "connected":
        raise HTTPException(409, "Mailbox binding mismatch")
    try:
        event = json.loads(raw)
        kind, data = event["type"], event["data"]
        email_id = str(UUID(data["email_id"]))  # Never interpolate provider-controlled URLs.
        token = credentials.get("api_key") or credentials.get("access_token")
        if not token:
            raise providers.ProviderError("credential_required")
        if kind == "email.received":
            received = await providers.provider_request("GET", "https://api.resend.com/emails/receiving/" + email_id,
                headers={"Authorization": "Bearer " + token}, params={"html_format": "cid"})
            if received.get("id") != email_id:
                raise providers.ProviderError("provider_identity_mismatch")
            message = await inbox_service.ingest(db, sender.id, inbound_event(received, event_id, sender))
            return {"status": "persisted", "inbound_message_id": str(message.id)}
        kinds = {"email.delivered": "delivered", "email.bounced": "bounce", "email.complained": "complaint"}
        if kind not in {*kinds, "email.sent"}:
            raise HTTPException(422, "Unsupported provider event")
        confirmed = await providers.provider_request("GET", "https://api.resend.com/emails/" + email_id,
            headers={"Authorization": "Bearer " + token})
        if confirmed.get("id") != email_id:
            raise providers.ProviderError("provider_identity_mismatch")
        from backend.mail_transport import reconcile_receipt
        message = await reconcile_receipt(db, sender, confirmed)
        integration_service.audit(db, integration, integration.user_id, "mail_receipt_verified")
        await db.commit()
        if kind == "email.sent":
            return {"status": "persisted", "message_id": str(message.id)}
        receipt = await outreach_service.record_delivery_event(db, message.id, email_id,
            str(integration.id) + ":" + event_id, kinds[kind])
        return {"status": "persisted", "delivery_event_id": str(receipt.id)}
    except providers.ProviderError as error:
        integration.last_error, integration.last_error_at = error.code, datetime.utcnow()
        if error.code == "reconnect_required":
            integration.status, integration.health, integration.reconnect_required = "error", error.code, True
        integration_service.audit(db, integration, integration.user_id, "mailbox_fetch_failed")
        await db.commit()
        raise HTTPException(503, error.code, headers={"Retry-After": "60"}) from None
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(422, "Invalid provider event") from None
