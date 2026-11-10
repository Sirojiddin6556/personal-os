"""Reads @HumoCardBot / @CardXabarBot from the user's own account and records notices.

One task per connected ``telegram_user`` integration. Only the two official
bank bots are read (identity verified: bot flag, exact username, pinned id
for Uzcard); only incoming, non-forwarded messages sent by the bot itself.
History before the connection is never imported: the first run stores the
latest message id per bank and processes only newer ones. Missed messages
(restart, network) are caught up by polling ``min_id`` every minute, and the
shared fingerprint makes forwarding the same notice by hand a no-op.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timezone
from typing import Any, AsyncIterator, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select

from src.db.session import async_session_factory
from src.integrations.models import Integration
from src.integrations.telegram import user_account
from src.integrations.telegram.user_account import PROVIDER, dec, make_client

logger = logging.getLogger("personal_os.bank_listener")

BANK_BOTS: Dict[str, Tuple[str, Optional[int]]] = {
    "humo": ("HumoCardBot", None),
    "uzcard": ("CardXabarBot", 915326936),
}
POLL_SECONDS = 60.0
SUPERVISE_SECONDS = 30.0


def trusted(msg: Any, bot_id: int) -> bool:
    """Incoming message written by the bank bot itself in the private chat."""
    return (
        not getattr(msg, "out", True)
        and getattr(msg, "fwd_from", None) is None
        and getattr(msg, "sender_id", None) == bot_id
        and getattr(msg, "chat_id", bot_id) == bot_id
        and bool(getattr(msg, "message", ""))
    )


def verified_bot(entity: Any, provider: str) -> bool:
    username, pinned_id = BANK_BOTS[provider]
    return (
        bool(getattr(entity, "bot", False))
        and (getattr(entity, "username", "") or "").lower() == username.lower()
        and (pinned_id is None or getattr(entity, "id", None) == pinned_id)
    )


async def _bot_context(workspace_id: UUID) -> Tuple[Optional[str], Optional[str]]:
    """(bot token, linked chat id) of the workspace's own bot, used to ask for categories."""
    from src.integrations.crypto import crypto_service

    async with async_session_factory() as s:
        res = await s.execute(
            select(Integration).where(
                Integration.workspace_id == workspace_id,
                Integration.provider == "telegram",
                Integration.status == "connected",
            )
        )
        integ = res.scalars().first()
    if integ is None:
        return None, None
    cfg = integ.config or {}
    token = crypto_service.decrypt_token(bytes.fromhex(cfg["enc_token"])) if cfg.get("enc_token") else None
    return token, cfg.get("chat_id")


async def _save_cfg(integration_id: UUID, **changes: Any) -> None:
    async with async_session_factory() as s:
        integ = await s.get(Integration, integration_id)
        if integ is None:
            return
        cfg = dict(integ.config or {})
        status = changes.pop("_status", None)
        error = changes.pop("_error", "keep")
        cfg.update(changes)
        integ.config = cfg
        if status:
            integ.status = status
        if error != "keep":
            integ.sync_error = error
        await s.commit()


class WorkspaceListener:
    def __init__(self, integration_id: UUID, workspace_id: UUID):
        self.integration_id = integration_id
        self.workspace_id = workspace_id
        self.last_ids: Dict[str, int] = {}
        self.lock = asyncio.Lock()

    async def run(self) -> None:
        from telethon import events

        async with async_session_factory() as s:
            integ = await s.get(Integration, self.integration_id)
            cfg = dict(integ.config or {}) if integ else {}
        session = dec(cfg.get("enc_session"))
        if not session:
            return
        client = make_client(session, int(cfg["api_id"]), dec(cfg["enc_api_hash"]) or "")
        await client.connect()
        try:
            if not await client.is_user_authorized():
                await _save_cfg(
                    self.integration_id,
                    _status="error",
                    _error="Сеанс завершён в Telegram (Настройки → Устройства). Подключите аккаунт заново.",
                )
                return

            entities: Dict[str, Any] = {}
            for provider, (username, _pinned) in BANK_BOTS.items():
                try:
                    entity = await client.get_entity(username)
                except Exception:
                    continue  # the user never talked to this bank bot
                if verified_bot(entity, provider):
                    entities[provider] = entity
                else:
                    logger.warning("Bank bot identity check failed for %s", provider)
            if not entities:
                await _save_cfg(
                    self.integration_id,
                    _error="В аккаунте нет чатов с @HumoCardBot или @CardXabarBot.",
                )

            self.last_ids = {k: int(v) for k, v in (cfg.get("last_ids") or {}).items()}
            for provider, entity in entities.items():
                if provider not in self.last_ids:
                    latest = await client.get_messages(entity, limit=1)
                    self.last_ids[provider] = latest[0].id if latest else 0
            await _save_cfg(
                self.integration_id,
                last_ids=self.last_ids,
                sources=sorted(entities),
                _error=None if entities else "keep",
            )
            by_chat = {entity.id: provider for provider, entity in entities.items()}

            async def _on_new(event) -> None:  # noqa: ANN001
                provider = by_chat.get(event.chat_id)
                if provider:
                    await self.process(provider, entities[provider].id, [event.message])

            if by_chat:  # never subscribe with an empty filter (that would match every chat)
                client.add_event_handler(_on_new, events.NewMessage(chats=list(by_chat), incoming=True))

            logger.info("Bank listener running for workspace %s: %s", self.workspace_id, ", ".join(entities) or "-")
            while client.is_connected():
                for provider, entity in entities.items():
                    try:
                        fresh = await client.get_messages(entity, min_id=self.last_ids.get(provider, 0), limit=100)
                    except Exception as ex:
                        logger.warning("Bank listener poll failed (%s)", type(ex).__name__)
                        continue
                    await self.process(provider, entity.id, list(reversed(fresh)))
                await asyncio.sleep(POLL_SECONDS)
        finally:
            await client.disconnect()

    async def process(self, provider: str, bot_id: int, messages: list) -> None:
        from src.integrations.telegram import bank_flow, handler

        async with self.lock:
            changed = False
            for msg in sorted(messages, key=lambda m: m.id):
                if msg.id <= self.last_ids.get(provider, 0):
                    continue
                self.last_ids[provider] = msg.id
                changed = True
                if not trusted(msg, bot_id):
                    continue
                token, chat_id = await _bot_context(self.workspace_id)
                if not chat_id:
                    logger.info("Bank notice skipped: workspace bot is not linked to a chat")
                    continue
                reset = handler._current_bot_token.set(token) if token else None
                try:
                    received = msg.date.astimezone(timezone.utc)
                    fp = bank_flow.fingerprint_raw(provider, int(msg.date.timestamp()), msg.message)
                    async with _tenant(self.workspace_id) as s:
                        await bank_flow.ingest(s, self.workspace_id, chat_id, provider, msg.message, received, fp, quiet=True)
                except Exception as ex:
                    logger.exception("Bank notice from account failed: %s", ex)
                finally:
                    if reset is not None:
                        handler._current_bot_token.reset(reset)
            if changed:
                await _save_cfg(self.integration_id, last_ids=self.last_ids)


@asynccontextmanager
async def _tenant(workspace_id: UUID) -> AsyncIterator[Any]:
    from src.integrations.telegram.handler import _tenant_session

    async with _tenant_session(workspace_id) as s:
        yield s


class BankListenerManager:
    """Keeps one listener task per connected account; restarts crashed ones."""

    def __init__(self) -> None:
        self.tasks: Dict[UUID, asyncio.Task] = {}
        self._loop: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._loop is None:
            self._loop = asyncio.create_task(self._supervise())
            logger.info("Bank listener manager started")

    async def stop(self) -> None:
        for task in [self._loop, *self.tasks.values()]:
            if task:
                task.cancel()
        for task in [self._loop, *self.tasks.values()]:
            if task:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self.tasks.clear()
        self._loop = None

    async def _supervise(self) -> None:
        while True:
            try:
                async with async_session_factory() as s:
                    res = await s.execute(
                        select(Integration.id, Integration.workspace_id).where(
                            Integration.provider == PROVIDER, Integration.status == "connected"
                        )
                    )
                    wanted = {row[0]: row[1] for row in res.all()}
                for iid, task in list(self.tasks.items()):
                    if iid not in wanted or task.done():
                        task.cancel()
                        self.tasks.pop(iid, None)
                for iid, ws in wanted.items():
                    if iid not in self.tasks:
                        self.tasks[iid] = asyncio.create_task(self._guard(WorkspaceListener(iid, ws)))
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logger.warning("Bank listener supervisor tick failed: %s", ex)
            await asyncio.sleep(SUPERVISE_SECONDS)

    @staticmethod
    async def _guard(listener: WorkspaceListener) -> None:
        try:
            await listener.run()
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logger.warning("Bank listener for %s stopped: %s", listener.workspace_id, type(ex).__name__)
            await asyncio.sleep(30)  # supervisor restarts it on the next tick


bank_listener_manager = BankListenerManager()

__all__ = ["bank_listener_manager", "trusted", "verified_bot", "user_account"]
