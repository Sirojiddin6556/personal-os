"""Notifications domain service with live real-time push integration."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.notifications.models import DeliveryAttempt, Notification
from src.domains.notifications.schemas import NotificationCreate
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event
from src.ws.manager import ws_manager


class NotificationService:
    """Operations for creating, dispatching and acknowledging user notifications."""

    async def create_notification(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        body: NotificationCreate,
    ) -> Notification:
        notif = Notification(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=body.user_id,
            title=body.title,
            body=body.body,
            channel=body.channel,
            priority=body.priority,
            status="pending",
        )
        session.add(notif)
        await publish_event(
            session=session,
            event_type="notification.created.v1",
            aggregate_type="notification",
            aggregate_id=notif.id,
            workspace_id=workspace_id,
            data={"user_id": str(notif.user_id), "title": notif.title, "priority": notif.priority},
        )
        await session.commit()
        await session.refresh(notif)

        # Real-time WebSocket broadcast to workspace
        await ws_manager.broadcast_to_workspace(
            workspace_id=workspace_id,
            event={
                "type": "notification.received",
                "notification_id": str(notif.id),
                "title": notif.title,
                "body": notif.body,
                "priority": notif.priority,
            },
        )

        return notif

    async def list_notifications(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        stmt = select(Notification).where(
            Notification.workspace_id == workspace_id,
            Notification.user_id == user_id,
        )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))

        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def mark_as_read(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        notification_id: UUID,
    ) -> Notification:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.workspace_id == workspace_id,
        )
        res = await session.execute(stmt)
        notif = res.scalar_one_or_none()
        if not notif:
            raise NotFoundError(resource="Notification", identifier=notification_id)

        notif.read_at = datetime.now(timezone.utc)
        notif.status = "read"
        await session.commit()
        await session.refresh(notif)
        return notif

    async def get_unread_count(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
    ) -> int:
        stmt = (
            select(func.count(Notification.id))
            .where(
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one() or 0


notification_service = NotificationService()
