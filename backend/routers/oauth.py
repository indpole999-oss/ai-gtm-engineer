"""OAuth callback authenticates a one-time capability, not a browser JWT."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from backend.config import settings
from backend.database import get_db
from backend.tenancy import get_current_workspace, get_workspace_db
from backend.integration_service import begin_google_oauth, complete_google_oauth

router=APIRouter()


@router.get("/oauth/google/start")
async def google_start(integration_id: UUID | None = None,ctx=Depends(get_current_workspace),db=Depends(get_workspace_db)):
    return await begin_google_oauth(db,ctx,integration_id)


@router.get("/oauth/google/callback")
async def google_callback(state: str=Query(min_length=32,max_length=128),code: str | None=Query(None,min_length=1,max_length=4096),error: str | None=Query(None,max_length=100),db=Depends(get_db)):
    if error:
        try:
            await complete_google_oauth(db,state,None)
        except HTTPException:
            return RedirectResponse(settings.FRONTEND_URL.rstrip("/")+"/settings?connection=failed",status_code=303)
    await complete_google_oauth(db,state,code)
    # Fixed server configuration, never a user-controlled redirect URI.
    return RedirectResponse(settings.FRONTEND_URL.rstrip("/")+"/settings?connection=success",status_code=303)
