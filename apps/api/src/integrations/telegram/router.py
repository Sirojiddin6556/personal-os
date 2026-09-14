"""Telegram Webhook & Integration Router with opaque UUID and secret token validation."""

import hmac
import logging
import secrets
import time
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.domains.identity.models import Workspace
from src.integrations.crypto import crypto_service
from src.integrations.models import Integration
from src.integrations.telegram.handler import handle_telegram_update
from src.shared.deps import get_db_session, get_public_session, get_workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])
integrations_telegram_router = APIRouter(prefix="/integrations/telegram", tags=["telegram-integration"])

_TELEGRAM_DEDUP_CACHE: Dict[str, float] = {}


async def deduplicate_telegram_update(update_id: str, ttl_seconds: int = 86400) -> bool:
    """Idempotency deduplication using Redis SETNX with fallback memory cache.

    Returns True if update_id is new, False if it is a duplicate.
    """
    key = f"tg:dedup:{update_id}"

    # 1. Try Redis SETNX
    try:
        from src.shared.idempotency import idempotency_service

        client = await idempotency_service.get_client()
        if client:
            # redis.set(..., nx=True, ex=...) returns True on success, None/False if key exists
            set_success = await client.set(key, "1", nx=True, ex=ttl_seconds)
            return bool(set_success)
    except Exception as ex:
        logger.warning("Redis deduplication failed (%s). Using fallback memory cache.", ex)

    # 2. In-memory cache fallback (single-process / dev / testing)
    now = time.time()
    for k in list(_TELEGRAM_DEDUP_CACHE.keys()):
        if _TELEGRAM_DEDUP_CACHE[k] < now:
            _TELEGRAM_DEDUP_CACHE.pop(k, None)

    if key in _TELEGRAM_DEDUP_CACHE:
        return False

    _TELEGRAM_DEDUP_CACHE[key] = now + ttl_seconds
    return True


@router.post("/{webhook_id}")
async def telegram_webhook(
    webhook_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_public_session),
) -> Dict[str, bool]:
    """Ingest Telegram updates using opaque Webhook UUID with Secret Token verification, Fast ACK, and deduplication."""
    # 1. Validate webhook_id as valid UUID
    try:
        webhook_uuid = UUID(webhook_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found or invalid identifier",
        )

    # 2. Look up active connected Telegram integration matching webhook_id
    stmt = select(Integration).where(
        Integration.provider == "telegram",
        Integration.status == "connected",
    )
    res = await session.execute(stmt)
    integrations = res.scalars().all()

    matching_integration: Optional[Integration] = None
    for integ in integrations:
        if integ.config and str(integ.config.get("webhook_id")) == str(webhook_uuid):
            matching_integration = integ
            break

    if not matching_integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found or integration is inactive",
        )

    # 3. Verify X-Telegram-Bot-Api-Secret-Token with constant-time comparison
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected_secret = (
        matching_integration.config.get("webhook_secret")
        or settings.telegram_webhook_secret
    )

    if expected_secret:
        if not secret or not hmac.compare_digest(secret, expected_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Telegram secret token",
            )

    # 4. Fast ACK Telegram immediately (<500ms SLA)
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON update payload",
        )

    # 5. Dedupe: Redis SETNX update_id (TTL 24h)
    update_id = str(update.get("update_id", ""))
    if update_id:
        is_new = await deduplicate_telegram_update(update_id)
        if not is_new:
            # Duplicate update acknowledged without re-processing
            return {"ok": True}

    # 6. Background task dispatch with workspace binding
    background_tasks.add_task(
        handle_telegram_update,
        update,
        workspace_id=matching_integration.workspace_id,
    )
    return {"ok": True}


class TelegramConnectRequest(BaseModel):
    bot_token: str = Field(min_length=10, description="Telegram Bot Token from @BotFather")
    webhook_url: Optional[str] = Field(default=None, description="Optional public HTTPS Webhook URL for Telegram updates")


@integrations_telegram_router.post("/connect")
async def connect_telegram(
    body: TelegramConnectRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Validate bot token with Telegram Bot API, configure opaque UUID webhook/secret, and store encrypted credentials."""
    token = body.bot_token.strip()

    # 1. Test token with Telegram Bot API
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        except Exception as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Не удалось связаться с Telegram API: {ex}",
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недействительный токен Telegram-бота. Проверьте токен, полученный от @BotFather.",
            )
        data = resp.json()
        if not data.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Telegram API вернул ошибку: {data.get('description')}",
            )
        bot_user = data.get("result", {})

    # 2. Generate unique opaque webhook_id and secret_token, encrypt bot token
    webhook_id = uuid4()
    webhook_secret = secrets.token_urlsafe(32)
    enc = crypto_service.encrypt_token(token)

    # 3. Form public HTTPS Webhook URL containing only opaque UUID (NO bot token in URL)
    webhook_registered = False
    target_webhook_url = None

    if body.webhook_url:
        raw_url = body.webhook_url.strip().rstrip("/")
        if "{webhook_id}" in raw_url:
            target_webhook_url = raw_url.format(webhook_id=webhook_id)
        elif "/webhooks/telegram" in raw_url:
            base_part = raw_url.split("/webhooks/telegram")[0]
            target_webhook_url = f"{base_part}/v1/webhooks/telegram/{webhook_id}"
        else:
            target_webhook_url = f"{raw_url}/v1/webhooks/telegram/{webhook_id}"
    elif getattr(settings, "telegram_webhook_base_url", ""):
        base_part = settings.telegram_webhook_base_url.strip().rstrip("/")
        if "/webhooks/telegram" in base_part:
            base_part = base_part.split("/webhooks/telegram")[0]
        target_webhook_url = f"{base_part}/v1/webhooks/telegram/{webhook_id}"

    # 4. Register setWebhook if a valid HTTPS URL is available
    if target_webhook_url and target_webhook_url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                wh_resp = await client.post(
                    f"https://api.telegram.org/bot{token}/setWebhook",
                    json={
                        "url": target_webhook_url,
                        "secret_token": webhook_secret,
                        "allowed_updates": ["message", "callback_query"],
                    },
                )
                if wh_resp.status_code == 200 and wh_resp.json().get("ok"):
                    webhook_registered = True
                else:
                    logger.warning("Telegram setWebhook returned error: %s", wh_resp.text)
        except Exception as ex:
            logger.warning("Failed to invoke Telegram setWebhook: %s", ex)

    mode = "webhook" if webhook_registered else "polling"
    config_data = {
        "bot_id": bot_user.get("id"),
        "username": bot_user.get("username"),
        "first_name": bot_user.get("first_name"),
        "can_join_groups": bot_user.get("can_join_groups"),
        "webhook_id": str(webhook_id),
        "webhook_secret": webhook_secret,
        "webhook_url": target_webhook_url if webhook_registered else None,
        "webhook_registered": webhook_registered,
        "mode": mode,
        "enc_token": enc["combined"].hex(),
    }

    # 5. Upsert Integration record
    stmt = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "telegram",
    )
    res = await session.execute(stmt)
    integration = res.scalar_one_or_none()

    if not integration:
        integration = Integration(
            id=uuid4(),
            workspace_id=workspace.id,
            provider="telegram",
            status="connected",
            config=config_data,
        )
        session.add(integration)
    else:
        integration.status = "connected"
        integration.config = config_data

    await session.commit()
    return {
        "status": "connected",
        "bot": {
            "username": bot_user.get("username"),
            "first_name": bot_user.get("first_name"),
        },
        "webhook_id": str(webhook_id),
        "mode": mode,
        "webhook_registered": webhook_registered,
        "webhook_url": target_webhook_url if webhook_registered else None,
    }


@integrations_telegram_router.get("/status")
async def get_telegram_status(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Get current Telegram bot connection status and webhook metadata."""
    stmt = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "telegram",
    )
    res = await session.execute(stmt)
    integration = res.scalar_one_or_none()

    if not integration or integration.status != "connected":
        return {"status": "disconnected", "bot": None}

    return {
        "status": "connected",
        "bot": {
            "username": integration.config.get("username"),
            "first_name": integration.config.get("first_name"),
        },
        "webhook_id": integration.config.get("webhook_id"),
        "mode": integration.config.get("mode", "polling"),
        "webhook_registered": integration.config.get("webhook_registered", False),
    }


@integrations_telegram_router.delete("")
@integrations_telegram_router.delete("/")
async def disconnect_telegram(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, str]:
    """Disconnect Telegram bot integration, delete webhook from Telegram API, and revoke secrets."""
    stmt = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "telegram",
    )
    res = await session.execute(stmt)
    integration = res.scalar_one_or_none()

    if integration:
        # 1. Try to delete webhook from Telegram Bot API using decrypted token
        enc_hex = integration.config.get("enc_token")
        if enc_hex:
            try:
                decrypted_token = crypto_service.decrypt_token(bytes.fromhex(enc_hex))
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{decrypted_token}/deleteWebhook",
                        json={"drop_pending_updates": False},
                    )
            except Exception as ex:
                logger.warning("Failed to delete Telegram webhook on disconnect: %s", ex)

        # 2. Mark integration as disconnected and invalidate webhook_id, secrets, and encrypted token
        integration.status = "disconnected"
        integration.config = {
            **integration.config,
            "webhook_id": None,
            "webhook_secret": None,
            "webhook_url": None,
            "webhook_registered": False,
            "mode": "disconnected",
            "enc_token": None,
        }
        await session.commit()

    return {"status": "disconnected"}
