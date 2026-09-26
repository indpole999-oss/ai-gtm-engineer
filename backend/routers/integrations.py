"""Workspace-owned provider connections; credentials never leave the service."""
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from backend.database import Integration, IntegrationAudit
from backend.tenancy import get_workspace_db, get_current_workspace
from backend.security import encrypt_credentials, decrypt_credentials
from backend import providers, integration_service as service

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class IntegrationCreate(BaseModel):
    category: str = Field(min_length=1, max_length=50)
    provider: str = Field(min_length=1, max_length=100)
    auth_type: str = "api_key"
    credentials: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    credentials: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    status: str | None = None


def integration_response(row):
    return {"id":str(row.id), "workspace_id":str(row.workspace_id), "user_id":str(row.user_id),
            "category":row.category, "provider":row.provider, "auth_type":row.auth_type,
            "config":{k:v for k,v in (row.config or {}).items() if k in {"calendar_id","instance_url","from_email"}},
            "status":row.status, "health":row.health, "scopes":row.scopes,
            "token_expires_at":row.token_expires_at, "reconnect_required":row.reconnect_required,
            "last_connected_at":row.last_connected_at, "last_error_at":row.last_error_at,
            "last_error":"Provider connection failed" if row.last_error else None,
            "created_at":row.created_at, "updated_at":row.updated_at}


def validate(category, provider, auth_type, credentials, config):
    try:
        providers.validate_connection(category,provider,auth_type,credentials,config)
    except providers.ProviderError as error:
        raise HTTPException(400,error.code) from None


@router.get("")
async def list_integrations(db=Depends(get_workspace_db)):
    rows=(await db.scalars(select(Integration).order_by(Integration.updated_at.desc()))).all()
    return {"status":"success","integrations":[integration_response(row) for row in rows]}


@router.get("/providers")
async def provider_contracts(db=Depends(get_workspace_db)):
    return [{"category":c.category,"provider":c.provider,"auth_types":c.auth_types,"config_keys":c.config_keys}
            for c in providers.CONTRACTS.values()]


@router.get("/{integration_id}")
async def get_integration(integration_id: UUID, db=Depends(get_workspace_db)):
    return integration_response(await service.connection(db,integration_id))


@router.post("")
async def create_integration(payload: IntegrationCreate, ctx=Depends(get_current_workspace), db=Depends(get_workspace_db)):
    service.require_encryption()
    category,provider=payload.category.lower().strip(),payload.provider.lower().strip()
    validate(category,provider,payload.auth_type,payload.credentials,payload.config)
    row=Integration(workspace_id=ctx.workspace_id,user_id=ctx.user_id,category=category,provider=provider,
                    auth_type=payload.auth_type,credentials=encrypt_credentials(payload.credentials),config=payload.config)
    db.add(row)
    await db.flush()
    service.audit(db,row,ctx.user_id,"connection_created")
    await db.commit()
    return integration_response(row)


@router.put("/{integration_id}")
async def update_integration(integration_id: UUID,payload: IntegrationUpdate,ctx=Depends(get_current_workspace),db=Depends(get_workspace_db)):
    row=await service.connection(db,integration_id,lock=True)
    if payload.status not in (None,"disconnected"):
        raise HTTPException(400,"Connection health must be verified by the provider")
    service.require_encryption()
    credentials=payload.credentials if payload.credentials is not None else decrypt_credentials(row.credentials)
    config=payload.config if payload.config is not None else row.config
    validate(row.category,row.provider,row.auth_type,credentials,config)
    row.credentials,row.config=encrypt_credentials(credentials),config
    row.status,row.health,row.reconnect_required="disconnected","unknown",False
    row.token_expires_at=None
    service.audit(db,row,ctx.user_id,"connection_updated")
    await db.commit()
    return integration_response(row)


@router.delete("/{integration_id}")
async def delete_integration(integration_id: UUID,ctx=Depends(get_current_workspace),db=Depends(get_workspace_db)):
    row=await service.connection(db,integration_id,lock=True)
    service.audit(db,row,ctx.user_id,"connection_deleted")
    await db.delete(row)
    await db.commit()
    return {"status":"success","message":"Local connection removed; revoke access at the provider if needed"}


@router.post("/{integration_id}/test")
async def test_integration(integration_id: UUID,ctx=Depends(get_current_workspace),db=Depends(get_workspace_db)):
    row=await service.connection(db,integration_id,lock=True)
    await service.test_connection(db,row,ctx.user_id)
    return {"status":"success" if row.health=="healthy" else "error",
            "integration":integration_response(row),"message":"Connection check complete"}


@router.post("/{integration_id}/revoke")
async def revoke_integration(integration_id: UUID,ctx=Depends(get_current_workspace),db=Depends(get_workspace_db)):
    row=await service.connection(db,integration_id,lock=True)
    credentials=decrypt_credentials(row.credentials)
    if row.provider=="google":
        try:
            await providers.GoogleOAuth().revoke(credentials.get("refresh_token") or credentials.get("access_token"))
        except providers.ProviderError:
            raise HTTPException(502,"Provider revocation failed; connection retained for retry") from None
    row.credentials=encrypt_credentials({})
    row.status,row.health,row.reconnect_required="disconnected","revoked",True
    service.audit(db,row,ctx.user_id,"connection_revoked")
    await db.commit()
    return {"status":"disconnected","provider_revoked":row.provider=="google",
            "message":"Revoke the token at the provider as well" if row.provider!="google" else "Provider access revoked"}


@router.get("/{integration_id}/audit")
async def integration_audit(integration_id: UUID,ctx=Depends(get_current_workspace),db=Depends(get_workspace_db)):
    ctx.require("owner","admin")
    await service.connection(db,integration_id)
    return (await db.scalars(select(IntegrationAudit).where(IntegrationAudit.integration_id==integration_id)
                            .order_by(IntegrationAudit.created_at.desc()))).all()
