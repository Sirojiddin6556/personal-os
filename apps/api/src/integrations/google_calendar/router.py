"""Google Calendar integration endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.integrations.google_calendar.sync import google_calendar_sync
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/integrations/google", tags=["integrations_google"])


class GoogleSyncPayload(BaseModel):
    events: Optional[List[Dict[str, Any]]] = None


@router.get("/auth-url")
async def get_auth_url(
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, str]:
    """Generate OAuth2 consent URL for Google Calendar."""
    return {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?scope=https://www.googleapis.com/auth/calendar&response_type=code",
    }


@router.post("/sync")
async def sync_calendar(
    body: GoogleSyncPayload,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Trigger manual or scheduled sync with Google Calendar."""
    return await google_calendar_sync.sync_workspace_calendar(
        session=session,
        workspace_id=workspace.id,
        incoming_events=body.events,
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def google_push_webhook(
    channel_id: Optional[str] = Header(None, alias="X-Goog-Channel-ID"),
    resource_id: Optional[str] = Header(None, alias="X-Goog-Resource-ID"),
) -> Dict[str, str]:
    """Google Calendar push notifications webhook endpoint."""
    return {"status": "acknowledged", "channel_id": channel_id or ""}
