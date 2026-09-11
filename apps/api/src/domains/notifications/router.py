"""Notifications API endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import User, Workspace
from src.domains.notifications.schemas import (
    NotificationCreate,
    NotificationResponse,
    UnreadCountResponse,
)
from src.domains.notifications.service import notification_service
from src.shared.deps import get_current_user, get_db_session, get_workspace

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> NotificationResponse:
    notif = await notification_service.create_notification(session, workspace.id, body)
    return NotificationResponse.model_validate(notif)


@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> List[NotificationResponse]:
    notifs = await notification_service.list_notifications(session, workspace.id, user.id, unread_only, limit, offset)
    return [NotificationResponse.model_validate(n) for n in notifs]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> NotificationResponse:
    notif = await notification_service.mark_as_read(session, workspace.id, notification_id)
    return NotificationResponse.model_validate(notif)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    count = await notification_service.get_unread_count(session, workspace.id, user.id)
    return UnreadCountResponse(unread_count=count)
