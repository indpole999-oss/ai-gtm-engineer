"""Contract and OAuth lifecycle tests use injected fake providers, never live APIs."""
from datetime import datetime, timedelta
import hashlib
from urllib.parse import urlparse, parse_qs
from uuid import UUID
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, update
from backend.config import settings
from backend.database import AsyncSessionLocal, OAuthAttempt, Integration, WorkspaceMembership
from backend.security import decrypt_credentials
from backend import providers
from backend.integration_service import GOOGLE_SCOPE
from test_workspace_security import signup


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings,"INTEGRATION_ENCRYPTION_KEY",Fernet.generate_key().decode())
    monkeypatch.setattr(settings,"GOOGLE_CLIENT_ID","test-client")
    monkeypatch.setattr(settings,"GOOGLE_CLIENT_SECRET","test-client-secret")
    monkeypatch.setattr(settings,"FRONTEND_URL","http://localhost:3000")


@pytest.fixture
def fake_google(monkeypatch):
    calls=[]
    class FakeGoogle:
        async def exchange(self,code,verifier):
            calls.append(("exchange",code,verifier))
            return {"access_token":"first-token","refresh_token":"refresh-one","scope":GOOGLE_SCOPE,"expires_in":3600}
        async def refresh(self,refresh_token):
            calls.append(("refresh",refresh_token))
            return {"access_token":"refreshed-token","refresh_token":"rotated-refresh","expires_in":3600}
        async def revoke(self,token):
            calls.append(("revoke",token))
            return {}
    monkeypatch.setattr(providers,"GoogleOAuth",FakeGoogle)
    class Healthy:
        async def verify(self,credentials,config):
            calls.append(("verify",credentials["access_token"]))
            return providers.ProviderHealth(scopes=[GOOGLE_SCOPE])
    monkeypatch.setattr(providers,"get_provider",lambda *args: Healthy())
    return calls


def start(client,headers,query=""):
    response=client.get("/api/v1/calendar/oauth/google/start"+query,headers=headers)
    assert response.status_code==200,response.text
    params=parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert params["code_challenge_method"]==["S256"]
    return params["state"][0]


def test_durable_oauth_replay_refresh_audit_revoke(client,configured,fake_google):
    headers=signup(client,"oauth@example.com")
    state=start(client,headers)
    async def inspect_attempt():
        async with AsyncSessionLocal() as db:
            row=await db.get(OAuthAttempt,hashlib.sha256(state.encode()).hexdigest())
            assert row is not None and row.consumed_at is None
            assert state not in row.encrypted_verifier
            assert len(decrypt_credentials(row.encrypted_verifier)["verifier"])>=43
    client.portal.call(inspect_attempt)
    result=client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"test-code"},follow_redirects=False)
    assert result.status_code==303,result.text
    assert result.headers["location"]=="http://localhost:3000/settings?connection=success"
    assert client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"test-code"}).status_code==400
    rows=client.get("/api/v1/integrations",headers=headers).json()["integrations"]
    assert len(rows)==1 and rows[0]["status"]=="connected"
    iid=rows[0]["id"]
    assert "first-token" not in str(rows) and "refresh-one" not in str(rows)
    async def expire():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]),workspace_role="owner")
            row=await db.get(Integration,UUID(iid))
            row.token_expires_at=datetime.utcnow()-timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire)
    assert client.post(f"/api/v1/integrations/{iid}/test",headers=headers).json()["status"]=="success"
    async def inspect_refresh():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]),workspace_role="owner")
            row=await db.get(Integration,UUID(iid))
            assert decrypt_credentials(row.credentials)["refresh_token"]=="rotated-refresh"
    client.portal.call(inspect_refresh)
    events=client.get(f"/api/v1/integrations/{iid}/audit",headers=headers).json()
    assert {event["action"] for event in events}>={"oauth_connected","token_refreshed","connection_tested"}
    assert client.post(f"/api/v1/integrations/{iid}/revoke",headers=headers).json()["provider_revoked"] is True
    assert ("revoke","rotated-refresh") in fake_google
    assert len([call for call in fake_google if call[0]=="exchange"])==1


def test_expired_and_revoked_membership_cannot_complete_oauth(client,configured,fake_google):
    headers=signup(client,"expired@example.com")
    state=start(client,headers)
    async def expire():
        async with AsyncSessionLocal() as db:
            attempt=await db.get(OAuthAttempt,hashlib.sha256(state.encode()).hexdigest())
            attempt.expires_at=datetime.utcnow()-timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire)
    assert client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"x"}).status_code==400
    state=start(client,headers)
    async def revoke_membership():
        async with AsyncSessionLocal() as db:
            membership=await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id==UUID(headers["X-Workspace-ID"])))
            membership.status="suspended"
            await db.commit()
    client.portal.call(revoke_membership)
    assert client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"x"}).status_code==403
    assert fake_google==[]


def test_cross_workspace_reconnect_and_connection_status_forgery(client,configured,fake_google):
    a,b=signup(client,"ca@example.com"),signup(client,"cb@example.com")
    created=client.post("/api/v1/integrations",headers=b,json={"category":"crm","provider":"hubspot","credentials":{"access_token":"secret"}})
    iid=created.json()["id"]
    assert client.get(f"/api/v1/calendar/oauth/google/start?integration_id={iid}",headers=a).status_code==404
    assert client.put(f"/api/v1/integrations/{iid}",headers=b,json={"status":"connected"}).status_code==400
    assert client.post(f"/api/v1/integrations/{iid}/revoke",headers=a).status_code==404


@pytest.mark.parametrize("category,provider,auth", [("crm","hubspot","api_key"),("crm","salesforce","oauth2"),("calendar","google","oauth2"),("email","gmail","oauth2"),("email","outlook","oauth2"),("email","resend","api_key"),("search","serper","api_key"),("enrichment","apollo","api_key")])
def test_provider_contracts_have_fixed_destinations(category,provider,auth,monkeypatch):
    import asyncio
    calls=[]
    async def fake_request(method,url,**kwargs):
        calls.append(url)
        return {}
    monkeypatch.setattr(providers,"provider_request",fake_request)
    config={"instance_url":"https://example.my.salesforce.com"} if provider=="salesforce" else {}
    credentials={"access_token":"not-a-real-token"}
    providers.validate_connection(category,provider,auth,credentials,config)
    result=asyncio.run(providers.HttpProvider(category,provider).verify(credentials,config))
    assert result.status in {"healthy","configured_unverified"}
    assert bool(calls)==(provider!="serper")


@pytest.mark.parametrize("url",["http://localhost","https://127.0.0.1","https://evil.test","https://example.my.salesforce.com@evil.test","https://example.my.salesforce.com:8443","https://example.my.salesforce.com/path"])
def test_salesforce_rejects_untrusted_destinations(url):
    with pytest.raises(providers.ProviderError):
        providers.salesforce_origin(url)


def test_declined_consent_consumes_state_and_returns_to_settings(client,configured,fake_google):
    headers=signup(client,"denied@example.com")
    state=start(client,headers)
    result=client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"error":"access_denied"},follow_redirects=False)
    assert result.status_code==303 and result.headers["location"].endswith("connection=failed")
    assert client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"x"}).status_code==400
    assert fake_google==[]


def test_access_revoked_during_provider_exchange_cannot_save_credentials(client,configured,monkeypatch):
    headers=signup(client,"race@example.com")
    state=start(client,headers)
    class RevokingProvider:
        async def exchange(self,code,verifier):
            async with AsyncSessionLocal() as db:
                row=await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id==UUID(headers["X-Workspace-ID"])))
                row.status="suspended"
                await db.commit()
            return {"access_token":"secret","scope":GOOGLE_SCOPE,"expires_in":3600}
    monkeypatch.setattr(providers,"GoogleOAuth",RevokingProvider)
    result=client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"x"})
    assert result.status_code==403
    async def verify_no_connection():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]),workspace_role="owner")
            assert (await db.scalars(select(Integration))).all()==[]
    client.portal.call(verify_no_connection)


def test_reconnect_retains_refresh_token_when_google_omits_it(client,configured,fake_google,monkeypatch):
    headers=signup(client,"reconnect@example.com")
    state=start(client,headers)
    assert client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"x"},follow_redirects=False).status_code==303
    iid=client.get("/api/v1/integrations",headers=headers).json()["integrations"][0]["id"]
    class ReconnectProvider:
        async def exchange(self,code,verifier):
            return {"access_token":"replacement","scope":GOOGLE_SCOPE,"expires_in":3600}
    monkeypatch.setattr(providers,"GoogleOAuth",ReconnectProvider)
    state=start(client,headers,f"?integration_id={iid}")
    assert client.get("/api/v1/calendar/oauth/google/callback",params={"state":state,"code":"x"},follow_redirects=False).status_code==303
    async def verify_persisted():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]),workspace_role="owner")
            rows=(await db.scalars(select(Integration))).all()
            assert len(rows)==1
            assert decrypt_credentials(rows[0].credentials)["refresh_token"]=="refresh-one"
    client.portal.call(verify_persisted)


def test_missing_credentials_never_fall_back_to_global_settings(monkeypatch):
    import asyncio
    monkeypatch.setattr(settings,"HUBSPOT_API_KEY","deployment-global-secret",raising=False)
    with pytest.raises(providers.ProviderError,match="credential_required"):
        asyncio.run(providers.HttpProvider("crm","hubspot").verify({},{}))
