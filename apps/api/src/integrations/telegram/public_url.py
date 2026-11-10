"""Follow the public URL of a Cloudflare Quick Tunnel.

A Quick Tunnel (``cloudflared tunnel --url ...``, no account, no domain) gets a
new ``*.trycloudflare.com`` hostname on every restart. cloudflared exposes it at
``http://<metrics>/quicktunnel`` as ``{"hostname": "..."}``.

When the hostname changes we:
- update runtime settings (web URL, Mini App URL, webhook base, Google redirect);
- re-register every connected bot: setWebhook + setChatMenuButton (Mini App);
- tell linked chats the new web address.

The web app and the Mini App call the API by relative path (/api), so nothing
has to be rebuilt.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import async_session_factory
from src.integrations.models import Integration

logger = logging.getLogger("personal_os.public_url")


def apply_public_url(base: str) -> None:
    """Point all URL-dependent settings at the new public base URL."""
    base = base.rstrip("/")
    settings.frontend_url = base
    settings.telegram_miniapp_url = f"{base}/tg/"
    settings.telegram_webhook_base_url = f"{base}/api"
    settings.google_redirect_uri = f"{base}/api/v1/integrations/google/callback"


async def _bot_call(client: httpx.AsyncClient, token: str, method: str, payload: Dict[str, Any]) -> bool:
    try:
        resp = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        ok = resp.status_code == 200 and resp.json().get("ok", False)
        if not ok:
            logger.warning("Telegram %s failed: %s", method, resp.text[:200])
        return ok
    except httpx.HTTPError as ex:
        logger.warning("Telegram %s error: %s", method, type(ex).__name__)
        return False


async def reconfigure_bots(session: AsyncSession, base: str, client: Optional[httpx.AsyncClient] = None) -> int:
    """Re-point every connected bot to ``base``. Returns how many bots were updated."""
    from src.integrations.crypto import crypto_service

    base = base.rstrip("/")
    res = await session.execute(
        select(Integration).where(Integration.provider == "telegram", Integration.status == "connected")
    )
    integrations = list(res.scalars().all())
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=15.0)
    updated = 0
    try:
        for integ in integrations:
            cfg = dict(integ.config or {})
            if cfg.get("public_url") == base:
                continue
            token: Optional[str] = None
            if cfg.get("enc_token"):
                try:
                    token = crypto_service.decrypt_token(bytes.fromhex(cfg["enc_token"]))
                except Exception as ex:
                    logger.warning("Cannot decrypt bot token of %s: %s", integ.id, type(ex).__name__)
            token = token or (settings.telegram_bot_token or None)
            if not token:
                continue

            if cfg.get("webhook_id"):
                hook = {
                    "url": f"{base}/api/v1/webhooks/telegram/{cfg['webhook_id']}",
                    "allowed_updates": ["message", "edited_message", "callback_query"],
                }
                if cfg.get("webhook_secret"):
                    hook["secret_token"] = cfg["webhook_secret"]
                if not await _bot_call(client, token, "setWebhook", hook):
                    # A fresh trycloudflare hostname may not resolve for Telegram yet:
                    # leave public_url untouched so the next tick retries.
                    continue
                cfg.update(webhook_url=hook["url"], webhook_registered=True, mode="webhook")

            await _bot_call(
                client,
                token,
                "setChatMenuButton",
                {"menu_button": {"type": "web_app", "text": "Открыть", "web_app": {"url": f"{base}/tg/"}}},
            )

            chat = cfg.get("chat_id")
            if chat:
                await _bot_call(
                    client,
                    token,
                    "sendMessage",
                    {"chat_id": chat, "text": f"🔗 Personal OS доступен по новому адресу:\n{base}/"},
                )

            cfg["public_url"] = base
            integ.config = cfg
            updated += 1
        await session.commit()
    finally:
        if own_client:
            await client.aclose()
    return updated


async def read_quick_tunnel_hostname(metrics_url: str, client: httpx.AsyncClient) -> Optional[str]:
    try:
        resp = await client.get(metrics_url)
        if resp.status_code != 200:
            return None
        host = (resp.json() or {}).get("hostname")
        return host or None
    except (httpx.HTTPError, ValueError):
        return None


class PublicUrlWatcher:
    def __init__(self, metrics_url: str, interval: float = 15.0):
        self.metrics_url = metrics_url
        self.interval = interval
        self.current: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Watching Quick Tunnel URL at %s", self.metrics_url)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def tick(self, client: httpx.AsyncClient) -> None:
        host = await read_quick_tunnel_hostname(self.metrics_url, client)
        if not host:
            return
        base = f"https://{host}"
        if base != self.current:
            apply_public_url(base)
            logger.info("Public URL is now %s", base)
            self.current = base
        # Retry bots every tick until each one is on the current URL (cheap: skipped when done).
        async with async_session_factory() as session:
            await reconfigure_bots(session, base, client)

    async def _loop(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                try:
                    await self.tick(client)
                except asyncio.CancelledError:
                    raise
                except Exception as ex:
                    logger.warning("Public URL watcher tick failed: %s", ex)
                await asyncio.sleep(self.interval)


public_url_watcher: Optional[PublicUrlWatcher] = (
    PublicUrlWatcher(settings.quick_tunnel_metrics_url) if settings.quick_tunnel_metrics_url else None
)
