"""Workspace connection lifecycle, durable OAuth and persistent refresh tokens."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from backend.config import settings
from backend.database import Integration, OAuthAttempt, IntegrationAudit, User, Workspace, WorkspaceMembership
from backend.security import encrypt_credentials, decrypt_credentials
from backend import providers

GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar"


def require_encryption():
    if not settings.INTEGRATION_ENCRYPTION_KEY:
        raise HTTPException(503, "Integration encryption is not configured")


def audit(db, integration, actor_id, action):
    db.add(IntegrationAudit(workspace_id=integration.workspace_id, integration_id=integration.id,
                            user_id=actor_id, action=action))


async def connection(db, integration_id, lock=False):
    query = select(Integration).where(Integration.id == integration_id)
    if lock:
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Integration not found")
    return row


async def refresh_if_needed(db, row, actor_id):
    credentials = decrypt_credentials(row.credentials)
    if row.token_expires_at and row.token_expires_at <= datetime.utcnow() + timedelta(seconds=60):
        if row.provider != "google" or not credentials.get("refresh_token"):
            row.status, row.health, row.reconnect_required = "error", "reconnect_required", True
            raise providers.ProviderError("reconnect_required")
        token = await providers.GoogleOAuth().refresh(credentials["refresh_token"])
        if not token.get("access_token"):
            raise providers.ProviderError("reconnect_required")
        credentials["access_token"] = token["access_token"]
        if token.get("refresh_token"):
            credentials["refresh_token"] = token["refresh_token"]
        row.credentials = encrypt_credentials(credentials)
        row.token_expires_at = datetime.utcnow() + timedelta(seconds=int(token.get("expires_in", 3600)))
        row.reconnect_required = False
        audit(db, row, actor_id, "token_refreshed")
        await db.flush()
    return credentials


async def test_connection(db, row, actor_id):
    try:
        credentials = await refresh_if_needed(db, row, actor_id)
        health = await providers.get_provider(row.category, row.provider).verify(credentials, row.config or {})
        row.health = health.status
        row.status = "connected" if health.status == "healthy" else "disconnected"
        row.scopes = health.scopes
        row.last_error = None
        row.reconnect_required = False
        if health.status == "healthy":
            row.last_connected_at = datetime.utcnow()
        audit(db, row, actor_id, "connection_tested")
    except providers.ProviderError as error:
        row.health, row.status = error.code, "error"
        row.last_error = error.code
        row.last_error_at = datetime.utcnow()
        row.reconnect_required = error.code == "reconnect_required"
        audit(db, row, actor_id, "connection_test_failed")
    except Exception:
        row.health, row.status, row.last_error = "error", "error", "provider_unavailable"
        row.last_error_at = datetime.utcnow()
        audit(db, row, actor_id, "connection_test_failed")
    await db.commit()
    return row


async def begin_google_oauth(db, ctx, integration_id=None):
    ctx.require("owner", "admin")
    require_encryption()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google OAuth is not configured")
    if integration_id:
        existing = await connection(db, integration_id)
        if (existing.category, existing.provider) != ("calendar", "google"):
            raise HTTPException(400, "Reconnect provider mismatch")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    attempt = OAuthAttempt(state_hash=hashlib.sha256(state.encode()).hexdigest(),
        workspace_id=ctx.workspace_id, user_id=ctx.user_id, integration_id=integration_id,
        encrypted_verifier=encrypt_credentials({"verifier": verifier}),
        expires_at=datetime.utcnow()+timedelta(minutes=10))
    db.add(attempt)
    await db.commit()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id":settings.GOOGLE_CLIENT_ID, "redirect_uri":settings.GOOGLE_REDIRECT_URI,
        "response_type":"code", "scope":GOOGLE_SCOPE, "state":state, "access_type":"offline",
        "prompt":"consent", "code_challenge":challenge, "code_challenge_method":"S256"})
    return {"authorization_url":url,"provider":"google","status":"authorization_required"}


async def complete_google_oauth(db, state, code):
    # This lookup is the one narrow pre-auth OAuth capability: an unguessable,
    # hashed, expiring, one-time token, followed by fresh user/membership checks.
    digest = hashlib.sha256(state.encode()).hexdigest()
    attempt = await db.get(OAuthAttempt, digest)
    now = datetime.utcnow()
    if attempt is None or attempt.consumed_at or attempt.expires_at <= now:
        raise HTTPException(400, "Invalid or expired OAuth state")
    membership_query = select(WorkspaceMembership).join(Workspace).join(User).where(
        WorkspaceMembership.workspace_id == attempt.workspace_id,
        WorkspaceMembership.user_id == attempt.user_id, WorkspaceMembership.status == "active",
        WorkspaceMembership.role.in_(["owner","admin"]), Workspace.status == "active", User.is_active.is_(True))
    membership = await db.scalar(membership_query)
    if membership is None:
        raise HTTPException(403, "Workspace access changed; restart connection")
    # Core UPDATE intentionally bypasses customer ORM bulk mutation rejection.
    # Conditional claim is atomic on both SQLite and PostgreSQL.
    connection_ = await db.connection()
    claim = await connection_.execute(update(OAuthAttempt).where(
        OAuthAttempt.state_hash == digest, OAuthAttempt.consumed_at.is_(None),
        OAuthAttempt.expires_at > now).values(consumed_at=now))
    if claim.rowcount != 1:
        raise HTTPException(400, "OAuth state already consumed")
    verifier = decrypt_credentials(attempt.encrypted_verifier)["verifier"]
    await db.commit()  # Consumed even if provider exchange fails; retry starts a new flow.
    db.info.update(workspace_id=attempt.workspace_id, workspace_role=membership.role)
    if not code:
        raise HTTPException(400, "OAuth authorization was declined; restart connection")
    try:
        token = await providers.GoogleOAuth().exchange(code, verifier)
        scopes = str(token.get("scope", "")).split()
        if not token.get("access_token") or GOOGLE_SCOPE not in scopes:
            raise providers.ProviderError("required_scope_missing")
        # Consent/network exchange may take time. Access must still be valid
        # when credentials are saved, not only when the OAuth flow began.
        membership = await db.scalar(membership_query.with_for_update().execution_options(populate_existing=True))
        if membership is None:
            raise HTTPException(403, "Workspace access changed; restart connection")
        db.info["workspace_role"] = membership.role
        row = await connection(db, attempt.integration_id, lock=True) if attempt.integration_id else None
        existing = decrypt_credentials(row.credentials) if row else {}
        payload = {"access_token":token["access_token"], "refresh_token":token.get("refresh_token") or existing.get("refresh_token"), "scopes":scopes}
        if row is None:
            row = Integration(workspace_id=attempt.workspace_id, user_id=attempt.user_id,
                category="calendar", provider="google", auth_type="oauth2", config={"calendar_id":"primary"})
            db.add(row)
        row.credentials = encrypt_credentials(payload)
        row.scopes, row.status, row.health = scopes, "connected", "healthy"
        row.token_expires_at = now + timedelta(seconds=int(token.get("expires_in", 3600)))
        row.reconnect_required, row.last_error = False, None
        row.last_connected_at = now
        await db.flush()
        audit(db, row, attempt.user_id, "oauth_connected")
        await db.commit()
        return row
    except (providers.ProviderError, ValueError, TypeError):
        raise HTTPException(400, "OAuth connection failed; restart connection") from None
