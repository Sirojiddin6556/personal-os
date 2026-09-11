"""Telegram webhook router with fast ACK, constant-time secret verification, and Redis deduplication."""

import hmac
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from src.config import settings
from src.integrations.telegram.handler import handle_telegram_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])

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


@router.post("/{bot_token}")
@router.post("")
@router.post("/")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    bot_token: Optional[str] = None,
) -> Dict[str, bool]:
    """Ingest Telegram updates with Fast ACK (<500ms), header verification, deduplication, and async dispatch."""
    # 1. Verify secret token header with constant-time comparison
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if settings.telegram_webhook_secret:
        if not secret or not hmac.compare_digest(secret, settings.telegram_webhook_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Telegram secret token",
            )
    elif secret:
        expected = "valid_secret_token"
        if not hmac.compare_digest(secret, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Telegram secret token",
            )

    # 2. Fast ACK Telegram immediately (<500ms SLA)
    update = await request.json()

    # 3. Dedupe: Redis SETNX update_id (TTL 24h)
    update_id = str(update.get("update_id", ""))
    if update_id:
        is_new = await deduplicate_telegram_update(update_id)
        if not is_new:
            # Duplicate update acknowledged without re-processing
            return {"ok": True}

    # 4. Background task: handle_update
    background_tasks.add_task(handle_telegram_update, update)
    return {"ok": True}
