"""Periodic Google Calendar pull for every connected workspace.

Google push notifications need a stable public URL (they are registered once per
channel); a self-hosted Quick Tunnel changes its address, so without a worker the
calendar only refreshed on a manual "Sync". This loop runs incremental_sync
(syncToken; falls back to a full sync on 410 / no token) every few minutes.
"""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from src.config import settings
from src.db.session import TENANT_INFO_KEY, async_session_factory, set_tenant_context
from src.integrations.google_calendar.sync import incremental_sync
from src.integrations.models import Integration

logger = logging.getLogger("personal_os.google_calendar")


async def connected_workspaces() -> List[UUID]:
    async with async_session_factory() as session:
        res = await session.execute(
            select(Integration.workspace_id)
            .where(Integration.provider == "google_calendar", Integration.status == "connected")
            .distinct()
        )
        return list(res.scalars().all())


async def sync_workspace(workspace_id: UUID) -> None:
    async with async_session_factory() as session:
        try:
            session.sync_session.info[TENANT_INFO_KEY] = str(workspace_id)
            await set_tenant_context(session, workspace_id)
            await incremental_sync(session, workspace_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def sync_all() -> int:
    """One pass over all connected workspaces; a failing one never stops the others."""
    done = 0
    for workspace_id in await connected_workspaces():
        try:
            await sync_workspace(workspace_id)
            done += 1
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logger.warning("Calendar sync failed for workspace %s: %s", workspace_id, ex)
    return done


class CalendarSyncScheduler:
    def __init__(self, interval: float):
        self.interval = interval
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self.interval <= 0 or self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Google Calendar auto-sync started (every %ss).", self.interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        await asyncio.sleep(30)  # let startup (migrations, tunnel URL) settle first
        while True:
            try:
                await sync_all()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logger.warning("Calendar auto-sync tick failed: %s", ex)
            await asyncio.sleep(self.interval)


calendar_sync_scheduler = CalendarSyncScheduler(interval=settings.calendar_sync_interval_seconds)
