"""Transactional Outbox implementation for reliable at-least-once domain event delivery."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)


class OutboxEvent(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Transactional Outbox event record stored atomically with domain state changes."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(nullable=False)
    aggregate_type: Mapped[str] = mapped_column(nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=5, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


async def publish_event(
    session: AsyncSession,
    event_type: str,
    aggregate_type: str,
    aggregate_id: UUID,
    workspace_id: UUID,
    data: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> OutboxEvent:
    """Stage a domain event into the outbox_events table within the active database transaction.

    This function does NOT commit the session. The caller is responsible for committing the
    business transaction atomically with this outbox entry.
    """
    event_payload = dict(data)
    if correlation_id:
        event_payload["_correlation_id"] = correlation_id

    event = OutboxEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=event_payload,
        status="pending",
        retry_count=0,
        max_retries=5,
        occurred_at=datetime.now(timezone.utc),
        published_at=None,
    )
    session.add(event)
    return event


class OutboxRelay:
    """Background service polling pending outbox events and dispatching them to subscribers."""

    def __init__(self, batch_size: int = 50, poll_interval: float = 2.0):
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background polling relay worker."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("OutboxRelay background worker started.")

    async def stop(self) -> None:
        """Stop the background polling relay worker gracefully."""
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("OutboxRelay background worker stopped.")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                processed_count = await self.process_batch()
                if processed_count == 0:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error("Error in OutboxRelay polling loop: %s", ex, exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def process_batch(self) -> int:
        """Fetch and publish a batch of pending events using FOR UPDATE SKIP LOCKED."""
        async with async_session_factory() as session:
            # Query pending events without tenant filter for universal relay
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .order_by(OutboxEvent.created_at.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            events: List[OutboxEvent] = list(result.scalars().all())

            if not events:
                return 0

            # Import ws manager here to avoid circular imports
            try:
                from src.ws.manager import ws_manager
            except ImportError:
                ws_manager = None

            now = datetime.now(timezone.utc)
            for ev in events:
                try:
                    # Broadcast event to active workspace WebSocket connections
                    if ws_manager:
                        await ws_manager.broadcast_to_workspace(
                            workspace_id=ev.workspace_id,
                            event={
                                "type": ev.event_type,
                                "aggregate_type": ev.aggregate_type,
                                "aggregate_id": str(ev.aggregate_id),
                                "payload": ev.payload,
                                "occurred_at": ev.occurred_at.isoformat(),
                            },
                        )
                    ev.status = "published"
                    ev.published_at = now
                except Exception as ex:
                    ev.retry_count += 1
                    ev.last_error = str(ex)
                    if ev.retry_count >= ev.max_retries:
                        ev.status = "failed"
                    logger.warning("Failed to dispatch outbox event %s: %s", ev.id, ex)

            await session.commit()
            return len(events)


outbox_relay = OutboxRelay()
