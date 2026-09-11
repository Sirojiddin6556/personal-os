"""Telegram webhook update parser and quick capture ingestion."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.models import InboxItem, Integration
from src.shared.outbox import publish_event

logger = logging.getLogger(__name__)


class TelegramWebhookHandler:
    """Processes incoming updates from Telegram Bot API."""

    async def handle_update(
        self,
        session: AsyncSession,
        update: Dict[str, Any],
    ) -> Optional[InboxItem]:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        text = message.get("text")
        if not text:
            return None

        chat = message.get("chat", {})
        chat_id = str(chat.get("id"))

        # Find integration associated with this Telegram chat
        stmt = (
            select(Integration)
            .where(
                Integration.provider == "telegram",
                Integration.status == "connected",
            )
        )
        res = await session.execute(stmt)
        integrations = res.scalars().all()

        target_workspace_id = None
        for integ in integrations:
            if integ.config.get("chat_id") == chat_id:
                target_workspace_id = integ.workspace_id
                break

        if not target_workspace_id and integrations:
            # Fallback to first configured integration if single-user bot
            target_workspace_id = integrations[0].workspace_id

        if not target_workspace_id:
            logger.warning("No workspace configured for Telegram chat %s", chat_id)
            return None

        # Capture into inbox_items
        inbox_item = InboxItem(
            id=uuid4(),
            workspace_id=target_workspace_id,
            source="telegram",
            raw_content=text,
            parsed_data={"chat_id": chat_id, "from": message.get("from", {})},
            status="pending",
        )
        session.add(inbox_item)

        await publish_event(
            session=session,
            event_type="inbox.item_captured.v1",
            aggregate_type="inbox_item",
            aggregate_id=inbox_item.id,
            workspace_id=target_workspace_id,
            data={"source": "telegram", "raw_content": text[:100]},
        )

        await session.commit()
        await session.refresh(inbox_item)
        return inbox_item


telegram_handler = TelegramWebhookHandler()
