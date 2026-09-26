"""Offline Phase 8 contracts with an independent durable, atomic provider ledger."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal, engine, Integration, WorkspaceMembership
from backend import execution_worker as worker, outcome_providers, outcome_service as service
from backend.outcome_models import OutcomeAction, CRMMapping, CalendarBooking, PipelineHistory, CRMReceipt
from backend.planning_models import ActionCommand
from backend.planning_service import digest
from backend.providers import ProviderError
from test_workspace_security import signup, company
from test_research import published, fake_research, create_job, execute_job  # noqa: F401
from test_outreach import provider  # noqa: F401
from test_inbox import sent, event, ingest
from test_planning_execution import approve

BASE = "/api/v1/outcomes"


class FakeTransport:
    simulated = durable_idempotency = atomic_versions = True
    def __init__(self, path):
        self.path, self.calls, self.mode = str(path), 0, "success"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS objects(namespace TEXT, kind TEXT, id TEXT, local_key TEXT, version INTEGER, properties TEXT, UNIQUE(namespace,kind,id), UNIQUE(namespace,kind,local_key))")
            db.execute("CREATE TABLE IF NOT EXISTS operations(namespace TEXT,key TEXT,receipt TEXT, UNIQUE(namespace,key))")
    async def lookup(self, namespace, key):
        if self.mode == "lookup_failure":
            raise ProviderError("provider_unavailable")
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT receipt FROM operations WHERE namespace=? AND key=?",(namespace,key)).fetchone()
        return json.loads(row[0]) if row else None
    async def fetch(self, namespace, kind, external_id):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT version,properties FROM objects WHERE namespace=? AND kind=? AND id=?",(namespace,kind,external_id)).fetchone()
        return {"version":str(row[0]),"properties":json.loads(row[1])} if row else None
    async def apply(self, namespace, key, request):
        self.calls += 1
        if self.mode == "failure":
            raise ProviderError("provider_rejected")
        if self.mode == "malformed":
            return {"status":"confirmed","id":"untrusted"}
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT receipt FROM operations WHERE namespace=? AND key=?",(namespace,key)).fetchone()
            if old:
                return json.loads(old[0])
            external = request["external_id"]
            current = db.execute("SELECT id,version FROM objects WHERE namespace=? AND kind=? AND " + ("id=?" if external else "local_key=?"), (namespace,request["object_type"],external or request["local_key"])).fetchone()
            if current:
                if request["expected_version"] != str(current[1]):
                    raise ProviderError("remote_conflict")
                external, version = current[0], current[1]+1
                db.execute("UPDATE objects SET version=?,properties=? WHERE namespace=? AND kind=? AND id=?", (version,json.dumps(request["properties"]),namespace,request["object_type"],external))
            else:
                if request["expected_version"]:
                    raise ProviderError("remote_conflict")
                external, version = external or "remote-"+key, 1
                db.execute("INSERT INTO objects VALUES(?,?,?,?,?,?)",(namespace,request["object_type"],external,request["local_key"],version,json.dumps(request["properties"])))
            receipt = {"status":"confirmed","id":external,"version":str(version),"request_hash":digest(request)}
            db.execute("INSERT INTO operations VALUES(?,?,?)",(namespace,key,json.dumps(receipt)))
        if self.mode == "lost_ack":
            raise RuntimeError("Lost provider response after committed operation")
        return receipt
    def count(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT count(*) FROM objects").fetchone()[0]


@pytest.fixture
def transport(tmp_path, monkeypatch):
    adapter = FakeTransport(tmp_path / "outcomes-provider.db")
    monkeypatch.setattr(outcome_providers, "transport_for", lambda integration, credentials: adapter)
    return adapter


def integration(client, a, category="crm", provider="hubspot"):
    async def create():
        async with AsyncSessionLocal() as db:
            worker.bind(db, UUID(a["X-Workspace-ID"]))
            membership = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            row = Integration(user_id=membership.user_id, category=category, provider=provider, credentials={"access_token":"fake-test-only"},
                status="connected",health="healthy",scopes=["https://www.googleapis.com/auth/calendar"] if category=="calendar" else [],config={"calendar_id":"primary"} if category=="calendar" else {})
            db.add(row)
            await db.flush()
            from backend.integration_service import audit
            audit(db,row,membership.user_id,"connection_created")
            await db.commit()
            return str(row.id)
    return client.portal.call(create)


def pipelines(client,a):
    r=client.get(BASE+"/pipeline",headers=a)
    assert r.status_code==200,r.text
    return r.json()


def get_action(client,a,action):
    return client.get(BASE+"/actions/"+action["id"],headers=a).json()


def crm_ready(client, transport):
    a=signup(client,"outcome@example.com")
    brain=published(client,a)
    account=company(client,a)
    pipeline=pipelines(client,a)[0]
    iid=integration(client,a)
    body={"pipeline_id":pipeline["id"],"integration_id":iid,"brain_version_id":brain["id"],"request_key":"crm-request-1","object_type":"company"}
    return a,body


def create(client,a,path,body):
    r=client.post(BASE+path,headers=a,json=body)
    assert r.status_code==201,r.text
    return r.json()


def run(client,a):
    return client.portal.call(worker.run_once,UUID(a["X-Workspace-ID"]))


def retry(client,a,action):
    r=client.post(BASE+"/actions/"+action["id"]+"/reconcile",headers=a)
    assert r.status_code==200,r.text


def test_crm_requires_approval_and_is_duplicate_safe(client,transport):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body)
    assert create(client,a,"/crm/sync",body)["id"]==action["id"]
    assert not run(client,a) and transport.calls==0
    approve(client,a,action["plan"])
    assert run(client,a)
    current=get_action(client,a,action)
    assert current["state"]=="confirmed" and current["external_id"]
    assert not run(client,a) and transport.count()==1 and transport.calls==1
    assert pipelines(client,a)[0]["stage"]=="discovered"
    assert client.post(BASE+"/crm/sync",headers=a,json={**body,"object_type":"opportunity"}).status_code==409
    mapping=client.get(BASE+"/crm/mappings",headers=a).json()[0]
    again=create(client,a,"/crm/sync",{**body,"request_key":"crm-update-2","expected_mapping_revision":mapping["revision"]})
    assert again["payload"]["external_id"]==current["external_id"]
    approve(client,a,again["plan"]);run(client,a)
    assert get_action(client,a,again)["state"]=="confirmed" and transport.count()==1


@pytest.mark.parametrize("mode",["failure","lost_ack","lookup_failure","malformed"])
def test_crm_failures_and_reconciliation(client,transport,mode):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    transport.mode=mode;run(client,a)
    assert get_action(client,a,action)["state"]!="confirmed"
    assert pipelines(client,a)[0]["stage"]=="discovered"
    client.portal.call(engine.dispose)
    transport.mode="success";retry(client,a,action);run(client,a)
    assert get_action(client,a,action)["state"]=="confirmed" and transport.count()==1
    assert transport.calls==(1 if mode in {"lost_ack","lookup_failure"} else 2)


def calendar_ready(client,fake_research,provider,transport):
    a,data,outbound=sent(client,fake_research,provider)
    incoming=ingest(client,a,data,event(outbound,body="Let's schedule a meeting."))
    run(client,a)
    incoming=client.get("/api/v1/inbox/messages/"+incoming["id"],headers=a).json()
    pipeline=next(p for p in pipelines(client,a) if p["contact_id"]==incoming["contact_id"])
    iid=integration(client,a,"calendar","google")
    start=datetime.now(timezone.utc)+timedelta(days=2)
    body={"pipeline_id":pipeline["id"],"integration_id":iid,"brain_version_id":incoming["brain_version_id"],
        "request_key":"calendar-request-1","inbound_message_id":incoming["id"],"classification_id":incoming["classification"]["id"],
        "title":"Reviewed discovery call","attendees":["jane@example.com"],"timezone":"UTC","start":start.isoformat(),"end":(start+timedelta(minutes=30)).isoformat()}
    return a,body


@pytest.mark.parametrize("mode",["success","failure","lost_ack","malformed"])
def test_calendar_approval_confirmation_and_restart(client,fake_research,provider,transport,mode):
    a,body=calendar_ready(client,fake_research,provider,transport)
    action=create(client,a,"/calendar/schedule",body)
    assert create(client,a,"/calendar/schedule",body)["id"]==action["id"]
    assert not run(client,a) and transport.calls==0
    assert client.post(BASE+"/calendar/schedule",headers=a,json={**body,"request_key":"different-request"}).status_code==409
    before=client.get(BASE+"/pipeline/"+body["pipeline_id"],headers=a).json()
    assert before["stage"]=="interested"
    approve(client,a,action["plan"]);transport.mode=mode;run(client,a)
    current=get_action(client,a,action)
    if mode!="success":
        assert current["meeting"]["status"]!="scheduled" and current["external_id"] is None
        assert client.get(BASE+"/pipeline/"+body["pipeline_id"],headers=a).json()["stage"]=="interested"
        client.portal.call(engine.dispose);transport.mode="success";retry(client,a,action);run(client,a)
    current=get_action(client,a,action)
    assert current["meeting"]["status"]=="scheduled" and current["meeting"]["provider_event_id"]==current["payload"]["event_id"]
    assert transport.count()==1
    assert client.get(BASE+"/pipeline/"+body["pipeline_id"],headers=a).json()["stage"]=="meeting"
    assert provider.calls==1


def test_pipeline_supported_transitions_and_manual_history(client,transport,fake_research):
    a,body=crm_ready(client,transport)
    p=pipelines(client,a)[0]
    path=BASE+"/pipeline/"+p["id"]+"/stage"
    for stage in ["qualified","contacted","engaged","interested","meeting","won"]:
        assert client.post(path,headers=a,json={"stage":stage,"expected_revision":p["revision"],"reason":"Reviewed unsupported outcome","reviewed":True}).status_code==409
    r=client.post(path,headers=a,json={"stage":"opportunity","expected_revision":p["revision"],"reason":"Customer explicitly opened opportunity","evidence_kind":"explicit_user","reviewed":True})
    assert r.status_code==200,r.text
    assert r.json()["stage"]=="opportunity"
    assert client.post(path,headers=a,json={"stage":"lost","expected_revision":p["revision"],"reason":"Stale customer update","evidence_kind":"explicit_user","reviewed":True}).status_code==409
    history=client.get(BASE+"/pipeline/"+p["id"],headers=a).json()["history"]
    assert len(history)==2 and history[1]["actor_id"] and history[1]["reason"]


@pytest.mark.parametrize("start,end,zone,valid",[
    ("2030-01-01T10:00:00+05:30","2030-01-01T10:30:00+05:30","Asia/Kolkata",True),
    ("2030-11-03T01:30:00-04:00","2030-11-03T01:45:00-04:00","America/New_York",True),
    ("2030-03-10T02:30:00-05:00","2030-03-10T03:30:00-04:00","America/New_York",False),
    ("2030-01-01T10:00:00","2030-01-01T10:30:00","UTC",False),
    ("2030-01-01T10:00:00+00:00","2030-01-01T09:30:00+00:00","UTC",False),
])
def test_timezone_handling(start,end,zone,valid):
    from fastapi import HTTPException
    if valid:
        a,b=service.normalize_times(datetime.fromisoformat(start),datetime.fromisoformat(end),zone)
        assert b>a and a.tzinfo is None
    else:
        with pytest.raises(HTTPException):
            service.normalize_times(datetime.fromisoformat(start),datetime.fromisoformat(end),zone)


def test_existing_remote_id_reused_and_conflicts_never_overwrite(client,transport):
    a,body=crm_ready(client,transport)
    with closing(sqlite3.connect(transport.path)) as db,db:
        db.execute("INSERT INTO objects VALUES(?,?,?,?,?,?)",(body["integration_id"],"companies","existing-42","known-local",4,json.dumps({"name":"External owner edit"})))
    action=create(client,a,"/crm/sync",{**body,"external_id":"existing-42","remote_version":"3"})
    approve(client,a,action["plan"]);run(client,a)
    assert get_action(client,a,action)["state"]=="conflict"
    assert transport.count()==1
    remote=client.portal.call(transport.fetch,body["integration_id"],"companies","existing-42")
    assert remote["properties"]["name"]=="External owner edit" and remote["version"]=="4"
    mapping=client.get(BASE+"/crm/mappings",headers=a).json()[0]
    event_body={"provider_event_id":"remote-event-1","mapping_id":mapping["id"],"external_id":"existing-42","remote_version":"4","properties":remote["properties"],"cursor":"cursor-4"}
    path=BASE+"/crm/simulated-events/"+body["integration_id"]
    first=client.post(path,headers=a,json=event_body)
    assert first.status_code==202,first.text
    assert client.post(path,headers=a,json=event_body).json()["id"]==first.json()["id"]
    assert client.post(path,headers=a,json={**event_body,"remote_version":"5"}).status_code==409
    mapping=client.get(BASE+"/crm/mappings/"+mapping["id"],headers=a).json()
    assert len(mapping["remote_events"])==1 and mapping["remote_version"]=="3"
    reviewed=client.post(BASE+"/crm/mappings/"+mapping["id"]+"/review-remote",headers=a,json={"receipt_id":first.json()["id"],"expected_revision":mapping["revision"],"reviewed":True})
    assert reviewed.status_code==200,reviewed.text
    next_action=create(client,a,"/crm/sync",{**body,"request_key":"reviewed-sync-2","expected_mapping_revision":reviewed.json()["revision"]})
    approve(client,a,next_action["plan"]);run(client,a)
    assert get_action(client,a,next_action)["state"]=="confirmed" and transport.count()==1
    assert get_action(client,a,next_action)["external_id"]=="existing-42"


@pytest.mark.parametrize("role",["viewer","member"])
def test_outcome_rbac_and_tenant_boundaries(client,transport,role):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body)
    b=signup(client,"other-outcome@example.com")
    for path in ["/actions/"+action["id"],"/pipeline/"+body["pipeline_id"],"/crm/mappings/"+action["mapping_id"],"/integration-health/"+body["integration_id"]]:
        assert client.get(BASE+path,headers=b).status_code==404
    assert client.get(BASE+"/pipeline",headers=b).json()==[]
    assert client.post(BASE+"/crm/sync",headers=b,json=body).status_code==404
    assert client.post(BASE+"/actions/"+action["id"]+"/reconcile",headers=b).status_code==404
    assert client.get(BASE+"/actions/"+action["id"]).status_code==401
    async def change():
        async with AsyncSessionLocal() as db:
            m=await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id==UUID(a["X-Workspace-ID"])))
            m.role=role
            await db.commit()
    client.portal.call(change)
    assert client.get(BASE+"/actions/"+action["id"],headers=a).status_code==200
    assert client.post(BASE+"/crm/sync",headers=a,json=body).status_code==403
    assert client.post(BASE+"/actions/"+action["id"]+"/reconcile",headers=a).status_code==403
    assert client.post(BASE+"/pipeline/"+body["pipeline_id"]+"/stage",headers=a,json={"stage":"won","expected_revision":1,"reason":"Explicit customer decision","evidence_kind":"explicit_user","reviewed":True}).status_code==403


def test_calendar_rechecks_suppression_at_dispatch_commit_gap(client,fake_research,provider,transport,monkeypatch):
    from backend.outreach_models import Suppression
    a,body=calendar_ready(client,fake_research,provider,transport)
    action=create(client,a,"/calendar/schedule",body);approve(client,a,action["plan"])
    original=service.authorize_dispatch
    calls=0
    async def interleaved(db,command,cycle,token):
        nonlocal calls
        calls+=1
        if calls==2:
            async with AsyncSessionLocal() as other:
                worker.bind(other,UUID(a["X-Workspace-ID"]))
                other.add(Suppression(email="jane@example.com",reason="unsubscribe"))
                await other.commit()
        return await original(db,command,cycle,token)
    monkeypatch.setattr(service,"authorize_dispatch",interleaved)
    run(client,a)
    assert calls==2 and transport.calls==0
    assert get_action(client,a,action)["state"]=="blocked"
    assert client.get(BASE+"/pipeline/"+body["pipeline_id"],headers=a).json()["stage"]!="meeting"


def test_calendar_intent_override_and_unapproved_requests_cannot_schedule(client,fake_research,provider,transport):
    a,body=calendar_ready(client,fake_research,provider,transport)
    action=create(client,a,"/calendar/schedule",body);approve(client,a,action["plan"])
    r=client.post("/api/v1/inbox/messages/"+body["inbound_message_id"]+"/override",headers=a,json={"category":"negative","reason":"Customer explicitly declined meeting","expected_number":1,"reviewed":True})
    assert r.status_code==201,r.text
    run(client,a)
    assert transport.calls==0 and get_action(client,a,action)["state"]=="blocked"
    assert client.post(BASE+"/calendar/schedule",headers=a,json={**body,"request_key":"new-invalid-intent"}).status_code==409


def test_crm_stale_local_revision_blocks_before_provider(client,transport,monkeypatch):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    original=service.authorize_dispatch
    calls=0
    async def interleaved(db,command,cycle,token):
        nonlocal calls
        calls+=1
        if calls==2:
            async with AsyncSessionLocal() as other:
                worker.bind(other,UUID(a["X-Workspace-ID"]))
                mapping=await other.scalar(select(CRMMapping).where(CRMMapping.id==UUID(action["mapping_id"])))
                mapping.revision+=1
                await other.commit()
        return await original(db,command,cycle,token)
    monkeypatch.setattr(service,"authorize_dispatch",interleaved)
    run(client,a)
    assert calls==2 and transport.calls==0 and get_action(client,a,action)["state"]=="conflict"


def test_outcome_expired_lease_recovery_and_stale_ack(client,transport):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    wid=UUID(a["X-Workspace-ID"])
    first=client.portal.call(worker.claim_next,wid)
    result=client.portal.call(worker.perform,wid,first)
    async def expire():
        async with AsyncSessionLocal() as db:
            worker.bind(db,wid)
            command=await db.scalar(select(ActionCommand).where(ActionCommand.id==first["id"]))
            command.lease_until=datetime.utcnow()-timedelta(seconds=1)
            await db.commit()
    client.portal.call(expire);client.portal.call(engine.dispose)
    second=client.portal.call(worker.claim_next,wid)
    assert second["token"]!=first["token"]
    client.portal.call(worker.finish,wid,first,result)
    result2=client.portal.call(worker.perform,wid,second)
    client.portal.call(worker.finish,wid,second,result2)
    assert result2==result and transport.count()==1 and transport.calls==1


def test_provider_success_requires_own_persisted_receipt(client,transport):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    wid=UUID(a["X-Workspace-ID"]);claim=client.portal.call(worker.claim_next,wid)
    client.portal.call(worker.finish,wid,claim,{"outcome_id":action["id"],"provider_object_id":"forged"})
    assert get_action(client,a,action)["state"]=="draft" and transport.calls==0
    async def check():
        async with AsyncSessionLocal() as db:
            worker.bind(db,wid)
            command=await db.scalar(select(ActionCommand))
            assert command.status=="queued" and command.error_code=="invalid_step_output"
    client.portal.call(check)


def test_contact_sync_reuses_legacy_identity_and_opportunity_is_explicit(client,transport):
    from backend.database import CRMRecord
    a,body=crm_ready(client,transport)
    account=pipelines(client,a)[0]
    contact=client.post("/api/v1/contacts/",headers=a,json={"company_id":account["company_id"],"first_name":"Jane","last_name":"Buyer","email":"jane@example.com"}).json()
    prospect=next(p for p in pipelines(client,a) if p["contact_id"]==contact["id"])
    async def legacy():
        async with AsyncSessionLocal() as db:
            worker.bind(db,UUID(a["X-Workspace-ID"]))
            db.add(CRMRecord(contact_id=UUID(contact["id"]),provider="hubspot",external_id="legacy-contact"))
            await db.commit()
    client.portal.call(legacy)
    contact_body={**body,"pipeline_id":prospect["id"],"object_type":"contact","request_key":"contact-sync-1"}
    assert client.post(BASE+"/crm/sync",headers=a,json=contact_body).status_code==409
    with closing(sqlite3.connect(transport.path)) as db,db:
        db.execute("INSERT INTO objects VALUES(?,?,?,?,?,?)",(body["integration_id"],"contacts","legacy-contact","legacy-local",1,json.dumps({"email":"jane@example.com"})))
    action=create(client,a,"/crm/sync",{**contact_body,"external_id":"legacy-contact","remote_version":"1"})
    approve(client,a,action["plan"]);run(client,a)
    assert get_action(client,a,action)["external_id"]=="legacy-contact" and transport.count()==1
    op_body={**body,"object_type":"opportunity","request_key":"opportunity-sync-1"}
    assert client.post(BASE+"/crm/sync",headers=a,json=op_body).status_code==409
    stage=client.post(BASE+"/pipeline/"+account["id"]+"/stage",headers=a,json={"stage":"opportunity","expected_revision":account["revision"],"reason":"Customer confirmed a real opportunity","evidence_kind":"explicit_user","reviewed":True})
    assert stage.status_code==200,stage.text
    assert client.post(BASE+"/crm/sync",headers=a,json=op_body).status_code==409
    action=create(client,a,"/crm/sync",{**op_body,"deal_pipeline_id":"explicit-pipeline","deal_stage_id":"explicit-stage"})
    approve(client,a,action["plan"]);run(client,a)
    assert get_action(client,a,action)["state"]=="confirmed" and transport.count()==2
    assert client.get(BASE+"/pipeline/"+account["id"],headers=a).json()["stage"]=="opportunity"


def test_supported_qualification_and_contacted_projection(client,fake_research,provider,transport):
    a,body=crm_ready(client,transport)
    account=pipelines(client,a)[0]
    assert account["stage"]=="discovered"
    job=create_job(client,a,{"id":body["brain_version_id"]},{"id":account["company_id"]})
    assert execute_job(client,a,job["id"]).status_code==200
    account=client.get(BASE+"/pipeline/"+account["id"],headers=a).json()
    assert account["stage"]=="qualified" and account["history"][-1]["evidence"]["research_job_id"]==job["id"]
    from test_outreach import ready,get_message
    b,data,reviewed,cycle=ready(client,fake_research)
    prospect=next(p for p in pipelines(client,b) if p["contact_id"]==data["enrollment"]["contact_id"])
    assert prospect["stage"]=="discovered"
    provider.mode="failure";run(client,b)
    assert client.get(BASE+"/pipeline/"+prospect["id"],headers=b).json()["stage"]=="discovered"
    from test_outreach import expire
    provider.mode="accepted";expire(client,b);run(client,b)
    assert get_message(client,b,reviewed)["state"]=="sent"
    assert client.get(BASE+"/pipeline/"+prospect["id"],headers=b).json()["stage"]=="contacted"


def test_local_edit_and_cancel_at_dispatch_gap_block_remote_write(client,transport,monkeypatch):
    from backend.database import Company
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    original=service.authorize_dispatch
    calls=0
    async def interleaved(db,command,cycle,token):
        nonlocal calls
        calls+=1
        if calls==2:
            async with AsyncSessionLocal() as other:
                worker.bind(other,UUID(a["X-Workspace-ID"]))
                row=await other.scalar(select(Company).where(Company.id==UUID(action["payload"]["company_id"])))
                row.name="Changed after approval"
                await other.commit()
        return await original(db,command,cycle,token)
    monkeypatch.setattr(service,"authorize_dispatch",interleaved)
    run(client,a)
    assert transport.calls==0 and get_action(client,a,action)["state"]=="blocked"


def test_default_live_provider_and_salesforce_fail_closed(client,transport,monkeypatch):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    monkeypatch.setattr(outcome_providers,"transport_for",lambda integration,credentials:outcome_providers.DisabledTransport())
    run(client,a)
    assert get_action(client,a,action)["state"]=="blocked" and transport.calls==0
    iid=integration(client,a,"crm","salesforce")
    assert client.post(BASE+"/crm/sync",headers=a,json={**body,"request_key":"unsupported-salesforce","integration_id":iid}).status_code==409


def test_pipeline_evidence_cannot_be_deleted_and_cross_record_evidence_rejected(client,transport):
    a,body=crm_ready(client,transport)
    account=pipelines(client,a)[0]
    assert client.delete("/api/v1/companies/"+account["company_id"],headers=a).status_code==409
    assert len(client.get(BASE+"/pipeline/"+account["id"],headers=a).json()["history"])==1


def test_google_refresh_survives_lost_ack_without_invalidating_approval(client,fake_research,provider,transport,monkeypatch):
    from cryptography.fernet import Fernet
    from backend.config import settings
    from backend.security import encrypt_credentials,decrypt_credentials
    from backend.providers import GoogleOAuth
    monkeypatch.setattr(settings,"INTEGRATION_ENCRYPTION_KEY",Fernet.generate_key().decode())
    a,body=calendar_ready(client,fake_research,provider,transport)
    async def expire_token():
        async with AsyncSessionLocal() as db:
            worker.bind(db,UUID(a["X-Workspace-ID"]))
            row=await db.scalar(select(Integration).where(Integration.id==UUID(body["integration_id"])))
            row.credentials=encrypt_credentials({"access_token":"expired-fake","refresh_token":"refresh-fake"})
            row.token_expires_at=datetime.utcnow()-timedelta(seconds=10)
            await db.commit()
    client.portal.call(expire_token)
    calls=[]
    async def refresh(self,token):
        calls.append(token)
        return {"access_token":"refreshed-fake","refresh_token":"rotated-fake","expires_in":3600}
    monkeypatch.setattr(GoogleOAuth,"refresh",refresh)
    action=create(client,a,"/calendar/schedule",body);approve(client,a,action["plan"])
    transport.mode="lost_ack";run(client,a)
    assert get_action(client,a,action)["state"]=="reconciling"
    client.portal.call(engine.dispose);transport.mode="success";retry(client,a,action);run(client,a)
    assert get_action(client,a,action)["state"]=="confirmed" and transport.count()==1 and transport.calls==1
    assert calls==["refresh-fake"]
    async def check():
        async with AsyncSessionLocal() as db:
            worker.bind(db,UUID(a["X-Workspace-ID"]))
            row=await db.scalar(select(Integration).where(Integration.id==UUID(body["integration_id"])))
            assert decrypt_credentials(row.credentials)["refresh_token"]=="rotated-fake"
    client.portal.call(check)


def test_cancelled_or_expired_approval_blocks_dispatch(client,transport,monkeypatch):
    a,body=crm_ready(client,transport)
    action=create(client,a,"/crm/sync",body);approve(client,a,action["plan"])
    original=service.authorize_dispatch
    calls=0
    async def interleaved(db,command,cycle,token):
        nonlocal calls
        calls+=1
        if calls==2:
            from backend.planning_models import ExecutionCycle
            async with AsyncSessionLocal() as other:
                worker.bind(other,UUID(a["X-Workspace-ID"]))
                row=await other.scalar(select(ExecutionCycle).where(ExecutionCycle.id==cycle.id))
                row.status="cancelled"
                await other.commit()
        return await original(db,command,cycle,token)
    monkeypatch.setattr(service,"authorize_dispatch",interleaved)
    run(client,a)
    assert calls==2 and transport.calls==0 and get_action(client,a,action)["state"]=="blocked"


def test_ooo_does_not_promote_engagement(client,fake_research,provider,transport):
    a,data,outbound=sent(client,fake_research,provider)
    incoming=ingest(client,a,data,event(outbound,body="I am out of office until Monday."))
    run(client,a)
    prospect=next(p for p in pipelines(client,a) if p["contact_id"]==incoming["contact_id"])
    assert prospect["stage"]=="contacted"


def test_calendar_time_rechecked_after_dispatch_preparation(client,fake_research,provider,transport,monkeypatch):
    a,body=calendar_ready(client,fake_research,provider,transport)
    start=datetime.now(timezone.utc)+timedelta(seconds=30)
    body.update(start=start.isoformat(),end=(start+timedelta(minutes=30)).isoformat())
    action=create(client,a,"/calendar/schedule",body);approve(client,a,action["plan"])
    original=service.integration_service.refresh_if_needed
    calls=0
    class AfterStart(datetime):
        @classmethod
        def utcnow(cls):
            return start.replace(tzinfo=None)+timedelta(seconds=1)
    async def delayed(db,row,actor):
        nonlocal calls
        calls+=1
        result=await original(db,row,actor)
        if calls==2:
            monkeypatch.setattr(service,"datetime",AfterStart)
        return result
    monkeypatch.setattr(service.integration_service,"refresh_if_needed",delayed)
    run(client,a)
    assert calls==2 and transport.calls==0 and get_action(client,a,action)["state"]=="blocked"
