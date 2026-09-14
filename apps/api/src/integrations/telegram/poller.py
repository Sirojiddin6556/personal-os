"""Background long-polling service for Telegram updates."""

import asyncio
import logging
from typing import Optional

import httpx

from src.config import settings
from src.integrations.telegram.handler import handle_telegram_update

logger = logging.getLogger("personal_os.telegram.poller")


class TelegramPoller:
    """Continuous async long-poller for Telegram Bot updates in local/non-webhook environments."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._running: bool = False
        self._last_offset: int = 0

    async def start(self) -> None:
        """Start the background polling task if token is available."""
        if not settings.telegram_bot_token or settings.telegram_bot_token in ("test", "mock-token", ""):
            logger.info("Telegram long-polling disabled (no valid bot token configured).")
            return

        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="telegram_poller")
        logger.info("Telegram background long-polling worker started.")

    async def stop(self) -> None:
        """Gracefully stop the background polling task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram background long-polling worker stopped.")

    async def _poll_loop(self) -> None:
        """Continuous polling loop fetching updates via Telegram getUpdates API."""
        while self._running:
            token = settings.telegram_bot_token.strip()
            if not token:
                await asyncio.sleep(5)
                continue

            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                params = {
                    "offset": self._last_offset,
                    "timeout": 15,
                    "allowed_updates": ["message", "edited_message", "callback_query"],
                }

                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("ok"):
                            updates = data.get("result", [])
                            for update in updates:
                                update_id = update.get("update_id", 0)
                                if update_id >= self._last_offset:
                                    self._last_offset = update_id + 1

                                try:
                                    await handle_telegram_update(update)
                                except Exception as ex:
                                    logger.exception("Error processing Telegram update %s: %s", update_id, ex)
                        else:
                            logger.warning("Telegram getUpdates returned not ok: %s", data.get("description"))
                            await asyncio.sleep(3)
                    elif resp.status_code == 409:
                        # Webhook might be active or another instance is polling
                        logger.warning("Telegram getUpdates conflict (409): webhook may be set or another poller is active.")
                        await asyncio.sleep(10)
                    else:
                        logger.warning("Telegram getUpdates HTTP %s: %s", resp.status_code, resp.text)
                        await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.warning("Telegram polling network error (%s). Retrying in 3s...", ex)
                await asyncio.sleep(3)


telegram_poller = TelegramPoller()
