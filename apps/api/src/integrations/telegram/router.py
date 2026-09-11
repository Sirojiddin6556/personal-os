"""Telegram webhook router."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import get_db_session
from src.integrations.telegram.handler import telegram_handler

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    update: Dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """Ingest Telegram updates sent by the Telegram Bot API webhook."""
    # Validate secret token if configured
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    await telegram_handler.handle_update(session, update)
    return {"status": "ok"}
