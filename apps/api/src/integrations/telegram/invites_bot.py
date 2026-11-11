"""Invitations from Telegram (instance owner only).

"пригласить Акмаль" -> a one-time sign-up link plus a ready text to forward;
"приглашения" -> active links with a revoke button. callback_data: ``iv:x:<invite uuid>``.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.config import settings
from src.db.session import async_session_factory
from src.domains.identity import invites
from src.domains.identity.models import Workspace
from src.integrations.models import Integration

INVITE_RE = re.compile(r"^(?:пригласить|пригласи|приглашение|инвайт)(?!\w)\s*(.*)$", re.I | re.S)
LIST_RE = re.compile(r"^(?:приглашения|инвайты)\s*$", re.I)


def base_url(integ_cfg: dict) -> str:
    url = (integ_cfg or {}).get("public_url") or settings.frontend_url or ""
    return str(url).rstrip("/")


def invite_link(base: str, code: str) -> str:
    return f"{base}/login?invite={code}"


def forward_text(link: str, days: int) -> str:
    return (
        "Привет! Приглашаю тебя в Personal OS — личные задачи, календарь, финансы и бот в Telegram. "
        "У тебя будет своё отдельное пространство, твоих данных никто не видит.\n\n"
        f"1) Открой ссылку и зарегистрируйся (email и пароль): {link}\n"
        "2) Для Telegram создай своего бота: напиши @BotFather → /newbot, придумай имя, "
        "скопируй токен и вставь его в Настройки → Интеграции → Telegram.\n\n"
        f"Ссылка одноразовая и действует {days} дн."
    )


async def _owner_context(ws: UUID) -> tuple[Optional[UUID], dict]:
    """(owner user id when this workspace belongs to the instance owner, telegram config)."""
    async with async_session_factory() as s:
        owner = (await s.execute(select(Workspace.owner_id).where(Workspace.id == ws))).scalar_one_or_none()
        cfg = (await s.execute(
            select(Integration.config).where(Integration.workspace_id == ws, Integration.provider == "telegram")
        )).scalars().first() or {}
        if owner is None or not await invites.is_instance_owner(s, owner):
            return None, cfg
        return owner, cfg


async def handle_command(ws: UUID, chat_id: Any, text: str) -> bool:
    """True when the message was an invite command (handled here)."""
    from src.integrations.telegram.handler import send_message

    listing = bool(LIST_RE.match(text))
    m = None if listing else INVITE_RE.match(text)
    if not listing and not m:
        return False
    owner, cfg = await _owner_context(ws)
    if owner is None:
        await send_message(chat_id, "Приглашать людей может только владелец этого сервера.")
        return True

    async with async_session_factory() as s:
        if listing:
            items = await invites.active(s)
            if not items:
                await send_message(chat_id, "Активных приглашений нет. Создать: «пригласить Имя».")
                return True
            tz = ZoneInfo(settings.default_timezone)
            lines = ["Активные приглашения:"]
            rows = []
            for inv in items:
                label = inv.note or "без имени"
                lines.append(f"• {label} — до {inv.expires_at.astimezone(tz):%d.%m %H:%M}")
                rows.append([{"text": f"🗑 Отозвать: {label}"[:60], "callback_data": f"iv:x:{inv.id}"}])
            await send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": rows})
            return True

        base = base_url(cfg)
        if not base.startswith("https://"):
            await send_message(chat_id, "Не знаю публичный адрес сервера — не могу собрать ссылку.")
            return True
        note = (m[1] if m else "").strip()
        invite, code = await invites.create(s, owner, note=note)
    link = invite_link(base, code)
    who = f" для «{invite.note}»" if invite.note else ""
    await send_message(
        chat_id,
        f"✅ Приглашение{who} создано: одноразовое, действует {invites.INVITE_DAYS} дн.\n{link}\n\n"
        "Ниже — текст, который можно переслать. Список и отзыв: «приглашения».\n"
        "⚠️ Адрес сервера временный: если он сменится до регистрации, создайте новое приглашение.",
        reply_markup={"inline_keyboard": [[{"text": "🗑 Отозвать", "callback_data": f"iv:x:{invite.id}"}]]},
    )
    await send_message(chat_id, forward_text(link, invites.INVITE_DAYS))
    return True


async def handle_callback(ws: UUID, chat_id: Any, message_id: Optional[int], data: str) -> None:
    from src.integrations.telegram.handler import edit_message, send_message

    parts = data.split(":")
    if len(parts) != 3 or parts[1] != "x":
        return
    try:
        invite_id = UUID(parts[2])
    except ValueError:
        return
    owner, _ = await _owner_context(ws)
    if owner is None:
        await send_message(chat_id, "Приглашать людей может только владелец этого сервера.")
        return
    async with async_session_factory() as s:
        done = await invites.revoke(s, invite_id)
    reply = "🗑 Приглашение отозвано — ссылка больше не работает." if done else "Это приглашение уже использовано, отозвано или истекло."
    if message_id:
        await edit_message(chat_id, message_id, reply)
    else:
        await send_message(chat_id, reply)
