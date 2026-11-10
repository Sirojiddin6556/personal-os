"""Deliver due planner reminders to the linked Telegram chat.

Runs inside the API process (like the outbox relay): every ``interval`` seconds it
picks reminders with ``remind_at <= now`` that were not delivered or dismissed and
sends them through the workspace's bot. On hosts that sleep when idle (Render free)
delivery happens when the instance wakes up — keep it awake with a health ping.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import async_session_factory
from src.domains.planner.models import PlannerReminder
from src.integrations.models import Integration
from src.integrations.telegram.handler import send_message

logger = logging.getLogger("personal_os.reminders")

# Reminders older than this are marked delivered without sending (e.g. after long downtime).
STALE_AFTER = timedelta(hours=12)


def _chat_and_token(integ: Integration) -> Tuple[Optional[str], Optional[str]]:
    cfg = integ.config or {}
    chat = cfg.get("tg_user_id") or cfg.get("chat_id")
    token: Optional[str] = None
    if cfg.get("enc_token"):
        from src.integrations.crypto import crypto_service

        try:
            token = crypto_service.decrypt_token(bytes.fromhex(cfg["enc_token"]))
        except Exception as ex:
            logger.warning("Cannot decrypt bot token of integration %s: %s", integ.id, type(ex).__name__)
    return (str(chat) if chat else None), token


async def deliver_due_reminders(session: AsyncSession, now: Optional[datetime] = None, limit: int = 50) -> int:
    """Send due reminders; returns how many were sent."""
    now = now or datetime.now(timezone.utc)
    res = await session.execute(
        select(PlannerReminder)
        .where(
            PlannerReminder.remind_at <= now,
            PlannerReminder.delivered_at.is_(None),
            PlannerReminder.is_dismissed.is_(False),
        )
        .order_by(PlannerReminder.remind_at)
        .limit(limit)
    )
    due = list(res.scalars().all())
    if not due:
        return 0

    res = await session.execute(
        select(Integration).where(Integration.provider == "telegram", Integration.status == "connected")
    )
    by_workspace: Dict[UUID, Integration] = {i.workspace_id: i for i in res.scalars().all()}

    sent = 0
    for reminder in due:
        integ = by_workspace.get(reminder.workspace_id)
        chat, token = _chat_and_token(integ) if integ else (None, None)
        if chat and now - reminder.remind_at <= STALE_AFTER:
            try:
                await send_message(chat, f"⏰ Напоминание: {reminder.title}", bot_token=token)
                sent += 1
            except Exception as ex:
                logger.warning("Reminder %s not delivered: %s", reminder.id, ex)
                continue  # retry on the next tick
        # Delivered, stale, or no chat linked: don't retry forever.
        reminder.delivered_at = now
    await session.commit()
    return sent


class ReminderDispatcher:
    def __init__(self, interval: float = 60.0):
        self.interval = interval
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Reminder dispatcher started (every %ss).", self.interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                async with async_session_factory() as session:
                    await deliver_due_reminders(session)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logger.warning("Reminder dispatcher tick failed: %s", ex)
            await asyncio.sleep(self.interval)


reminder_dispatcher = ReminderDispatcher(interval=settings.reminder_poll_interval_seconds)
