"""Run on the isolated migrated PostgreSQL service; no real provider traffic."""
import asyncio
import sys
import tempfile
from pathlib import Path
from datetime import datetime,timedelta
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
sys.path.insert(0,str(Path.cwd()/"tests"))
from backend.main import app
from backend.database import AsyncSessionLocal,engine
from backend import outcome_service as service, outcome_providers, execution_worker as worker, outreach_service
from backend.outcome_models import MODELS,PipelineRecord,OutcomeAction,CRMMapping
from backend.planning_models import ActionCommand
from backend.tenancy import WorkspaceContext
from test_outcomes import FakeTransport,crm_ready,calendar_ready,create,get_action,retry
from test_outreach import FakeProvider
from test_planning_execution import approve
from test_research import fake_research

role=sys.argv[1]
assert role.startswith("gaps_role_") and role.replace("_","").isalnum()
with tempfile.TemporaryDirectory() as directory,pytest.MonkeyPatch.context() as patch:
    transport=FakeTransport(Path(directory)/"provider.db")
    patch.setattr(outcome_providers,"transport_for",lambda integration,credentials:transport)
    provider=FakeProvider(str(Path(directory)/"outreach.db"))
    patch.setattr(outreach_service,"delivery_provider",lambda sender:provider)
    fake=fake_research.__wrapped__(patch)
    import test_outreach
    original_signup=test_outreach.signup
    patch.setattr(test_outreach,"signup",lambda client,email:original_signup(client,"phase8-"+email))
    with TestClient(app) as client:
        a,body=crm_ready(client,transport)
        wid=UUID(a["X-Workspace-ID"])
        uid=UUID(client.get("/api/v1/auth/me",headers=a).json()["id"])
        async def prepare():
            async with AsyncSessionLocal() as db:
                worker.bind(db,wid)
                action=await service.create_action(db,WorkspaceContext(wid,uid,"owner"),service.CRMInput(**body),"crm_sync")
                return action.id
        async def simultaneous():
            ids=await asyncio.gather(prepare(),prepare())
            assert ids[0]==ids[1]
            return ids[0]
        aid=client.portal.call(simultaneous)
        action=client.get("/api/v1/outcomes/actions/"+str(aid),headers=a).json()
        approve(client,a,action["plan"])
        async def claimed():
            claims=await asyncio.gather(worker.claim_next(wid),worker.claim_next(wid))
            assert sum(c is not None for c in claims)==1
            return next(c for c in claims if c)
        claim=client.portal.call(claimed)
        transport.mode="lost_ack"
        with pytest.raises(RuntimeError):
            client.portal.call(worker.perform,wid,claim)
        async def expire():
            async with AsyncSessionLocal() as db:
                worker.bind(db,wid)
                command=await db.scalar(select(ActionCommand).where(ActionCommand.id==claim["id"]))
                command.lease_until=datetime.utcnow()-timedelta(seconds=1)
                await db.commit()
            await engine.dispose()
        client.portal.call(expire)
        transport.mode="success"
        newer=client.portal.call(worker.claim_next,wid)
        result=client.portal.call(worker.perform,wid,newer)
        client.portal.call(worker.finish,wid,claim,result)
        client.portal.call(worker.finish,wid,newer,result)
        assert get_action(client,a,action)["state"]=="confirmed" and transport.count()==1 and transport.calls==1
        mapping=client.get("/api/v1/outcomes/crm/mappings",headers=a).json()[0]
        async def receipt():
            async with AsyncSessionLocal() as db:
                worker.bind(db,wid)
                await service.receive_crm_event(db,UUID(body["integration_id"]),service.CRMEvent(provider_event_id="pg-event",mapping_id=UUID(mapping["id"]),external_id=mapping["external_id"],remote_version=mapping["remote_version"],properties=mapping["remote_snapshot"]))
        client.portal.call(receipt)
        b,calendar_body=calendar_ready(client,fake,provider,transport)
        booking=create(client,b,"/calendar/schedule",calendar_body)
        approve(client,b,booking["plan"])
        client.portal.call(worker.run_once,UUID(b["X-Workspace-ID"]))
        assert get_action(client,b,booking)["meeting"]["status"]=="scheduled" and transport.count()==2
        async def security():
            async with AsyncSessionLocal() as db:
                worker.bind(db,wid)
                connection=await db.connection()
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                for model in MODELS:
                    flags=(await connection.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=:name"),{"name":model.__tablename__})).one()
                    assert flags==(True,True)
                assert await connection.scalar(text("SELECT count(*) FROM outcome_actions"))==1
                assert await connection.scalar(text("SELECT count(*) FROM calendar_bookings"))==0
                try:
                    await connection.execute(text("UPDATE outcome_actions SET external_id='forged' WHERE id=:id"),{"id":aid})
                except DBAPIError as error:
                    assert "immutable" in str(error)
                    await db.rollback()
                else:
                    raise AssertionError("Confirmed receipt was mutable")
                connection=await db.connection()
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                try:
                    await connection.execute(text("INSERT INTO pipeline_history(id,workspace_id,pipeline_id,source_key,to_stage,applied,source,reason,evidence,created_at) VALUES(:id,:wid,:pid,'forged','won',true,'test','bad','{}',now())"),{"id":uuid4(),"wid":wid,"pid":UUID(calendar_body["pipeline_id"])})
                except DBAPIError as error:
                    assert "foreign key" in str(error).lower()
                    await db.rollback()
                else:
                    raise AssertionError("Cross-tenant history accepted")
                connection=await db.connection()
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                await connection.execute(text("SELECT set_config('app.workspace_id',:wid,true)"),{"wid":str(uuid4())})
                for model in MODELS:
                    assert await connection.scalar(text("SELECT count(*) FROM "+model.__tablename__))==0
            await engine.dispose()
        client.portal.call(security)
