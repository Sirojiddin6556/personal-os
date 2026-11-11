"""Telegram update handler: intent classification, account pairing and command dispatch."""

import hashlib
import json
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import TENANT_INFO_KEY, async_session_factory, set_tenant_context
from src.domains.finance import learning
from src.domains.finance.bank_notices import learnable_merchant, merchant_key, provider_from_forward
from src.domains.finance.schemas import TransactionCreate
from src.domains.finance.service import finance_service
from src.domains.planner.schemas import PlannerReminderCreate
from src.domains.planner.service import planner_service
from src.domains.tasks.schemas import TaskCreate
from src.domains.tasks.service import task_service
from src.integrations.models import InboxItem, Integration
from src.shared.outbox import publish_event

logger = logging.getLogger(__name__)

# Token of the bot that received the current update (per-workspace bots are
# connected in the UI and stored encrypted; the global TELEGRAM_BOT_TOKEN is a fallback).
_current_bot_token: ContextVar[Optional[str]] = ContextVar("telegram_bot_token", default=None)

PAIRING_TTL_SECONDS = 15 * 60
PAIRING_RE = re.compile(r"^POS-[A-Z0-9]{6}$")
_PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class TelegramIntent:
    """Classified intent result from natural language message."""

    def __init__(self, intent_type: str, data: Dict[str, Any], confidence: float = 1.0):
        self.type = intent_type
        self.data = data
        self.confidence = confidence

    def __repr__(self) -> str:
        return f"TelegramIntent(type={self.type!r}, data={self.data!r})"


def format_amount(amount: float) -> str:
    if float(amount).is_integer():
        return f"{amount:,.0f}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ")


def confirm_keyboard(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inline keyboard to confirm an expense. callback_data is limited to 64 bytes."""
    amount = data.get("amount", 0)
    category = str(data.get("category", "прочее"))
    payload = f"confirm_expense:{amount}:"
    room = 64 - len(payload.encode("utf-8"))
    category = category.encode("utf-8")[:room].decode("utf-8", errors="ignore")
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Подтвердить", "callback_data": payload + category},
                {"text": "❌ Отмена", "callback_data": "cancel_expense"},
            ]
        ]
    }


def _resolve_token(bot_token: Optional[str]) -> Optional[str]:
    token = bot_token or _current_bot_token.get() or settings.telegram_bot_token
    if not token or token.startswith("mock-") or token in ("test", "dev"):
        return None
    return token.strip()


async def _bot_api(method: str, payload: Dict[str, Any], bot_token: Optional[str] = None) -> Dict[str, Any]:
    token = _resolve_token(bot_token)
    if token is None:
        logger.info("[Mock Telegram %s] %s", method, payload)
        return {"ok": True, "result": {"message_id": 99999, **payload}}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        resp.raise_for_status()
        return resp.json()


async def send_message(
    chat_id: int | str,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    bot_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a message via the bot that received the current update."""
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _bot_api("sendMessage", payload, bot_token)


async def edit_message(
    chat_id: int | str,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Replace the text/buttons of a bot message (falls back to a new message)."""
    payload: Dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        return await _bot_api("editMessageText", payload)
    except Exception as ex:  # e.g. message too old to edit
        logger.info("editMessageText failed (%s); sending a new message", ex)
        return await send_message(chat_id, text, reply_markup=reply_markup)


async def answer_callback(callback_id: str, text: Optional[str] = None) -> None:
    """Stop the loading spinner on an inline button."""
    payload: Dict[str, Any] = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        await _bot_api("answerCallbackQuery", payload)
    except Exception as ex:  # never fail the update because of the spinner
        logger.warning("answerCallbackQuery failed: %s", ex)


# ---------------------------------------------------------------------------
# Chat -> workspace resolution and pairing
# ---------------------------------------------------------------------------
async def _telegram_integrations(s: AsyncSession, integration_id: Optional[UUID] = None) -> List[Integration]:
    stmt = select(Integration).where(Integration.provider == "telegram", Integration.status == "connected")
    if integration_id is not None:
        stmt = stmt.where(Integration.id == integration_id)
    res = await s.execute(stmt)
    return list(res.scalars().all())


async def get_workspace_by_telegram_chat(
    chat_id: int | str,
    session: Optional[AsyncSession] = None,
    integration_id: Optional[UUID] = None,
) -> Optional[UUID]:
    """Resolve the workspace explicitly linked to this chat (no fallbacks)."""
    chat_str = str(chat_id)

    async def _query(s: AsyncSession) -> Optional[UUID]:
        for integ in await _telegram_integrations(s, integration_id):
            cfg = integ.config or {}
            if str(cfg.get("chat_id")) == chat_str or str(cfg.get("tg_user_id")) == chat_str:
                return integ.workspace_id
        # No fallback: an unknown chat must link itself first (pairing code or the Mini App).
        return None

    if session is not None:
        return await _query(session)
    async with async_session_factory() as s:
        return await _query(s)


def hash_pairing_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def new_pairing_code() -> str:
    return "POS-" + "".join(secrets.choice(_PAIRING_ALPHABET) for _ in range(6))


async def redeem_pairing_code(
    s: AsyncSession,
    code: str,
    chat_id: int | str,
    tg_user_id: Optional[int],
    integration_id: Optional[UUID] = None,
) -> Optional[UUID]:
    """Link the chat to the workspace that issued this one-time code. Returns the workspace id."""
    code_hash = hash_pairing_code(code)
    now = int(time.time())
    for integ in await _telegram_integrations(s, integration_id):
        cfg = dict(integ.config or {})
        stored = cfg.get("pairing_hash")
        if stored and secrets.compare_digest(str(stored), code_hash):
            if int(cfg.get("pairing_expires", 0)) < now:
                return None
            user_id = cfg.pop("pairing_user_id", None)
            cfg.pop("pairing_hash", None)
            cfg.pop("pairing_expires", None)
            cfg["chat_id"] = str(chat_id)
            if tg_user_id is not None:
                cfg["tg_user_id"] = tg_user_id
            if user_id:
                cfg["user_id"] = user_id
            integ.config = cfg
            await s.commit()
            return integ.workspace_id
    return None


@asynccontextmanager
async def _tenant_session(workspace_id: UUID) -> AsyncIterator[AsyncSession]:
    """Session bound to the workspace's RLS context for every transaction."""
    async with async_session_factory() as s:
        s.sync_session.info[TENANT_INFO_KEY] = str(workspace_id)
        await set_tenant_context(s, workspace_id)
        yield s


async def record_expense(
    s: AsyncSession, workspace_id: UUID, amount: float, category: str
) -> Optional[Tuple[Any, Any]]:
    """Post an expense immediately: cash account (created if missing), automatic category.

    Returns (transaction, account, category name, why).
    """
    from src.domains.finance import auto_category
    from src.domains.finance.schemas import AccountCreate

    accounts = [a for a in await finance_service.list_accounts(s, workspace_id) if not a.is_archived]
    account = next((a for a in accounts if a.account_type == "cash"), None)
    if account is None:
        account = await finance_service.create_account(
            s, workspace_id, AccountCreate(name="Наличные", type="cash", currency="UZS")
        )
    resolved, why = await auto_category.resolve(s, workspace_id, "expense", category)
    tx = await finance_service.post_transaction(
        s,
        workspace_id,
        TransactionCreate(
            account_id=account.id,
            amount_minor=int(round(amount * 100)),
            currency=account.currency,
            transaction_type="expense",
            category_id=resolved.id,
            note=f"Telegram: {category}",
        ),
    )
    return tx, account, resolved.name, why


# Bot users are in Uzbekistan by default; times like "в 19:00" are local.
REMINDER_TZ = ZoneInfo(settings.default_timezone)


def parse_reminder(raw: str, now: Optional[datetime] = None) -> Tuple[str, datetime]:
    """'позвонить маме в 19:00' / 'завтра в 9:30 врач' -> (title, aware UTC datetime)."""
    now_local = (now or datetime.now(timezone.utc)).astimezone(REMINDER_TZ)
    text = raw.strip()
    day_offset = 0
    m_day = re.search(r"(?:^|\s)(послезавтра|завтра|сегодня)(?=\s|$)", text, re.IGNORECASE)
    if m_day:
        day_offset = {"сегодня": 0, "завтра": 1, "послезавтра": 2}[m_day.group(1).lower()]
        text = (text[: m_day.start()] + " " + text[m_day.end():]).strip()
    # "через 2 часа", "через 15 минут", "через час", "через полчаса"
    m_in = re.search(
        r"(?:^|\s)через\s+(?:(\d+(?:[.,]5)?|полчаса|пару)\s*)?(минут[уы]?|мин\.?|час(?:а|ов)?|ч\.?)?(?=\s|$)",
        text, re.IGNORECASE,
    )
    # "в 19:00", "в 9.30", "в 7 30", "в 9 утра", "в 7 вечера", "в 19 часов", "к 10"
    m_time = re.search(
        r"(?:(?:^|\s)(?:в|к|на)\s+)?(\d{1,2})[:.](\d{2})(?=\s|$)"
        r"|(?:^|\s)(?:в|к)\s+(\d{1,2})(?:\s+(\d{2}))?(?:\s+(утра|дня|вечера|ночи|час(?:а|ов)?))?(?=\s|$)",
        text, re.IGNORECASE,
    )
    hour = minute = None
    if m_time:
        hour = int(m_time.group(1) or m_time.group(3))
        minute = int(m_time.group(2) or m_time.group(4) or 0)
        part = (m_time.group(5) or "").lower()
        if part in ("дня", "вечера") and hour < 12:
            hour += 12
        elif part == "ночи" and hour == 12:
            hour = 0
        elif not part and m_time.group(3) and 1 <= hour <= 6:
            hour += 12  # "в 5" said in conversation means 17:00
    if m_in and (m_in.group(1) or m_in.group(2)) and not m_time:
        amount_raw = (m_in.group(1) or "1").lower()
        unit = (m_in.group(2) or "час").lower()
        amount = {"полчаса": 30, "пару": 2}.get(amount_raw)
        if amount_raw == "полчаса":
            delta = timedelta(minutes=30)
        else:
            value = float(amount if amount is not None else amount_raw.replace(",", "."))
            delta = timedelta(minutes=value) if unit.startswith("мин") else timedelta(hours=value)
        target = now_local + delta
        text = (text[: m_in.start()] + " " + text[m_in.end():]).strip()
    elif hour is not None and hour < 24 and minute < 60:
        target = (now_local + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if day_offset == 0 and target <= now_local:
            target += timedelta(days=1)
        text = (text[: m_time.start()] + " " + text[m_time.end():]).strip()
    elif day_offset:
        target = (now_local + timedelta(days=day_offset)).replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        target = now_local + timedelta(hours=1)
    title = re.sub(r"\s+", " ", text).strip(" ,.:-") or "Напоминание"
    return title[:1].upper() + title[1:], target.astimezone(timezone.utc)


def looks_like_bank_notice(text: str) -> bool:
    """Pasted (not forwarded) card notification: signed amount in UZS plus a card mask."""
    return bool(
        re.search(r"^\s*(?:➖|➕)\s*\d", text, re.M)
        and re.search(r"UZS|сум", text, re.I)
        and re.search(r"\*{1,}\d{4}", text)
    )


NOT_LINKED_TEXT = (
    "Этот чат ещё не привязан к Personal OS.\n\n"
    "Откройте приложение кнопкой «Открыть» внизу или получите код в веб-версии "
    "(Настройки → Интеграции → Telegram) и отправьте его сюда."
)


async def ai_parse_telegram_message(text: str, workspace_id: UUID) -> TelegramIntent:
    """Parse raw text message using LLM or rule-based deterministic extractor."""
    clean_text = text.strip()
    lower_text = clean_text.lower()

    # 1. Check for AI OpenAI completions if configured
    if settings.openai_api_key and not settings.openai_api_key.startswith("sk-dummy"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                prompt = (
                    "Classify the following user message into exactly one intent JSON:\n"
                    "- CREATE_TASK: {\"type\": \"CREATE_TASK\", \"data\": {\"title\": \"...\"}}\n"
                    "- CREATE_EXPENSE: {\"type\": \"CREATE_EXPENSE\", \"data\": {\"amount\": 500, \"category\": \"кафе\"}}\n"
                    "- CREATE_REMINDER: {\"type\": \"CREATE_REMINDER\", \"data\": {\"title\": \"...\"}}\n"
                    "- UNKNOWN: {\"type\": \"UNKNOWN\", \"data\": {}}\n\n"
                    f"Message: {clean_text}\n"
                    "JSON response only:"
                )
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                    },
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return TelegramIntent(parsed.get("type", "UNKNOWN"), parsed.get("data", {}))
        except Exception as ex:
            logger.warning("LLM parser failed (%s), using rule-based fallback.", ex)

    # 2. Rule-based / regex parser
    # Expense pattern: "Расход: 500 руб кафе", "Потратил 1500 руб супермаркет", "Чек 300 р кофе"
    expense_match = re.search(
        r"(?:расход|потратил|купил|чек|spent)\s*:?\s*(\d+(?:[\.,]\d+)?)\s*(?:руб|рублей|р|₽|\$|usd|eur|€)?\s*(?:на|в|за)?\s*(.*)",
        lower_text,
    )
    if expense_match:
        amount_raw = expense_match.group(1).replace(",", ".")
        amount = float(amount_raw)
        category = expense_match.group(2).strip() or "прочее"
        return TelegramIntent(
            "CREATE_EXPENSE",
            {"amount": amount, "category": category, "currency": "UZS"},
        )

    # Direct expense pattern: "45000 такси", "120 тыс обед", "350 сум кофе"
    direct_expense = re.match(
        r"^(\d[\d ]*(?:[\.,]\d+)?)\s*(?:(тыс\.?|к)(?=\s|$))?\s*"
        r"(?:(?:сум[а-я]*|uzs|руб[а-я]*|р\.?|₽)(?=\s|$))?\s*(?:(?:на|в|за)(?=\s|$))?\s*(.*)$",
        lower_text,
    )
    if direct_expense and not re.match(r"^\d{1,2}:\d{2}", lower_text):
        amount = float(direct_expense.group(1).replace(" ", "").replace(",", "."))
        if direct_expense.group(2):
            amount *= 1000
        category = direct_expense.group(3).strip() or "прочее"
        return TelegramIntent(
            "CREATE_EXPENSE",
            {"amount": amount, "category": category, "currency": "UZS"},
        )

    # Task pattern: "Задача: Купить молоко", "Сделать презентацию", "todo: Review PR"
    task_match = re.search(
        r"^(?:задача|таск|сделать|todo|task)\s*:?\s*(.+)$",
        clean_text,
        re.IGNORECASE,
    )
    if task_match:
        title = task_match.group(1).strip()
        return TelegramIntent("CREATE_TASK", {"title": title, "priority": "medium"})

    # Reminder pattern: "Напоминание: в 18:00 встреча", "Напомни позвонить врачу"
    reminder_match = re.search(
        r"^(?:напоминание|напомни|remind|reminder)\s*:?\s*(.+)$",
        clean_text,
        re.IGNORECASE,
    )
    if reminder_match:
        title = reminder_match.group(1).strip()
        return TelegramIntent("CREATE_REMINDER", {"title": title, "body": title})

    # Greeting / Help pattern
    greetings = {
        "привет", "салам", "здравствуйте", "здравствуй", "добрый день",
        "доброе утро", "добрый вечер", "хай", "hello", "hi", "hey",
        "/help", "помощь", "start", "/start"
    }
    if lower_text in greetings or lower_text.startswith(("/start", "/help")):
        return TelegramIntent("GREETING", {})

    return TelegramIntent("UNKNOWN", {})


async def handle_telegram_update(
    update: Dict[str, Any],
    session: Optional[AsyncSession] = None,
    workspace_id: Optional[UUID] = None,
    bot_token: Optional[str] = None,
    integration_id: Optional[UUID] = None,
) -> None:
    """Process one Telegram update.

    ``workspace_id`` is a trusted override for internal callers only. Webhooks pass
    the bot's token / integration and the workspace is resolved from the linked chat,
    so strangers writing to a public bot cannot reach anyone's workspace.
    """
    reset = _current_bot_token.set(bot_token) if bot_token else None
    try:
        await _handle_update(update, session, workspace_id, integration_id)
    finally:
        if reset is not None:
            _current_bot_token.reset(reset)


async def _voice_to_text(chat_id: Any, media: Dict[str, Any]) -> str:
    """Recognized text of a voice message ('' when nothing to do; the user is told why)."""
    from src.integrations.telegram import voice

    if not settings.voice_enabled:
        await send_message(chat_id, "Голосовые выключены на этом сервере — напишите текстом.")
        return ""
    try:
        voice.check_media(media)
    except voice.VoiceError as ex:
        await send_message(chat_id, str(ex))
        return ""
    status = await send_message(chat_id, "🎙 Распознаю голосовое…")
    status_id = (status.get("result") or {}).get("message_id")

    async def say(reply: str) -> None:
        if status_id:
            await edit_message(chat_id, status_id, reply)
        else:
            await send_message(chat_id, reply)

    try:
        audio = await voice.download(str(media.get("file_id") or ""), _resolve_token(None))
        text = await voice.engine.transcribe(audio)
    except voice.VoiceError as ex:
        await say(str(ex))
        return ""
    except Exception as ex:
        logger.exception("Voice recognition failed: %s", ex)
        await say("Не получилось распознать голосовое. Попробуйте ещё раз или напишите текстом.")
        return ""
    if not text:
        await say("🎙 Ничего не расслышал — запишите ещё раз, поближе к микрофону.")
        return ""
    await say(f"🎙 «{text}»")
    return voice.normalize(text)


async def _handle_update(
    update: Dict[str, Any],
    session: Optional[AsyncSession],
    workspace_id: Optional[UUID],
    integration_id: Optional[UUID],
) -> None:
    # 1. Inline keyboard callbacks (expense confirmation)
    callback_query = update.get("callback_query")
    if callback_query:
        await _handle_callback(callback_query, session, workspace_id, integration_id)
        return

    # 2. Message details
    message = update.get("message") or update.get("edited_message") or {}
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    from_id = (message.get("from") or {}).get("id")
    from src.integrations.telegram import voice

    media = voice.media_of(message) if not text and "edited_message" not in update else None
    if not chat_id or (not text and media is None):
        return

    # 3. "/start CODE" or a bare one-time pairing code
    parts = text.split()
    candidate = (parts[1] if text.startswith("/start") and len(parts) > 1 else text).upper()
    if PAIRING_RE.match(candidate):
        if session is not None:
            linked = await redeem_pairing_code(session, candidate, chat_id, from_id, integration_id)
        else:
            async with async_session_factory() as s:
                linked = await redeem_pairing_code(s, candidate, chat_id, from_id, integration_id)
        await send_message(
            chat_id,
            "✅ Telegram привязан к Personal OS. Пишите задачи и расходы прямо сюда."
            if linked
            else "Код не подошёл или истёк. Получите новый в веб-версии: Настройки → Интеграции → Telegram.",
        )
        return

    if not workspace_id:
        workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session, integration_id=integration_id)
    if not workspace_id:
        await send_message(chat_id, NOT_LINKED_TEXT)
        return

    # 3b. Voice message: recognize on this server, then handle the text like a typed one
    if media is not None:
        text = await _voice_to_text(chat_id, media)
        if not text:
            return
        message = {**message, "text": text}

    # 4. Bank notification forwarded from @HumoCardBot / @CardXabarBot
    provider = provider_from_forward(message) if "edited_message" not in update else None
    if provider:
        from src.integrations.telegram import bank_flow

        async def _bank(s: AsyncSession) -> None:
            await bank_flow.handle_forward(s, workspace_id, chat_id, message, provider, text)

        if session is not None:
            await _bank(session)
        else:
            async with _tenant_session(workspace_id) as s:
                await _bank(s)
        return
    if looks_like_bank_notice(text):
        await send_message(
            chat_id,
            "Похоже на уведомление банка. Перешлите его (кнопка «Переслать») прямо из @HumoCardBot "
            "или @CardXabarBot — скопированный текст я не записываю, его нельзя проверить.",
        )
        return

    # 4b. Monthly spending limit: "лимит", "лимит 5 млн", "лимит выкл"
    from src.integrations.telegram import daily

    limit_match = daily.LIMIT_RE.match(text)
    if limit_match:
        async def _limit(s: AsyncSession) -> None:
            await daily.handle_limit_command(s, workspace_id, chat_id, limit_match[1])

        if session is not None:
            await _limit(session)
        else:
            async with _tenant_session(workspace_id) as s:
                await _limit(s)
        return

    # 4c. Invitations (instance owner): "пригласить Имя", "приглашения"
    from src.integrations.telegram import invites_bot

    if await invites_bot.handle_command(workspace_id, chat_id, text):
        return

    # 5. Dispatch intent
    async def _dispatch(s: AsyncSession) -> None:
        intent = await ai_parse_telegram_message(text, workspace_id)
        task = None
        reminder = None

        match intent.type:
            case "GREETING":
                await send_message(
                    chat_id,
                    "👋 Привет! Я ассистент Personal OS.\n\n"
                    "📋 Задачи:\n• Задача: купить билеты\n• Сделать: подготовить презентацию\n\n"
                    "💳 Расходы:\n• 45000 такси\n• Потратил 120 тыс на обед\n"
                    "• Пересылайте сюда уведомления @HumoCardBot и @CardXabarBot — запишу сам\n\n"
                    "⏰ Напоминания:\n• Напомни выпить витамины\n\n"
                    "📊 Лимит трат на месяц: «лимит 5 млн», посмотреть — «лимит»\n\n"
                    "🎙 Всё это можно надиктовать голосовым — распознаю здесь же, на сервере.\n\n"
                    "👥 Пригласить человека в своё отдельное пространство: «пригласить Имя»\n\n"
                    "📥 Любой другой текст сохраню во «Входящие» — разберёте одной кнопкой.\n"
                    "☀️ В 08:00 пришлю план дня, 🌙 в 21:00 — итоги.\n\n"
                    "Всё остальное — в приложении: кнопка «Открыть» внизу.",
                )

            case "CREATE_TASK":
                task_data = TaskCreate(**intent.data) if isinstance(intent.data, dict) else intent.data
                task = await task_service.create(s, workspace_id, task_data)
                await send_message(chat_id, f"✅ Задача создана: {task.title}")

            case "CREATE_EXPENSE":
                # Recorded right away, category chosen automatically; one tap to undo.
                amount = float(intent.data["amount"])
                label = str(intent.data["category"])
                tx, account, cat_name, why = await record_expense(s, workspace_id, amount, label)
                await send_message(
                    chat_id,
                    f"✅ Записано: {format_amount(amount)} сум · {label} → «{cat_name}» ({why}) · {account.name}",
                    reply_markup={"inline_keyboard": [[{"text": "↩️ Отменить", "callback_data": f"txu:{tx.id}"}]]},
                )

            case "CREATE_REMINDER":
                title, remind_at = parse_reminder(str(intent.data.get("title") or text))
                reminder = await planner_service.create_reminder(
                    s, workspace_id, PlannerReminderCreate(title=title, remind_at=remind_at)
                )
                await s.commit()
                local = remind_at.astimezone(REMINDER_TZ)
                await send_message(chat_id, f"⏰ Напомню {local:%d.%m в %H:%M}: {reminder.title}")

            case _:
                pass  # kept in the inbox below; the user sorts it with one tap

        entity_type: Optional[str] = None
        entity_id: Optional[UUID] = None
        item_status = "pending"  # only messages nobody understood stay pending
        if task is not None:
            entity_type, entity_id, item_status = "task", task.id, "processed"
        elif reminder is not None:
            entity_type, entity_id, item_status = "reminder", reminder.id, "processed"
        elif intent.type == "CREATE_EXPENSE":
            entity_type, entity_id, item_status = "transaction", tx.id, "processed"
        elif intent.type == "GREETING" or text.startswith("/"):
            item_status = "discarded"  # "processed" requires a linked entity (DB check)
            if intent.type != "GREETING":
                await send_message(chat_id, "Такой команды нет. Напишите «помощь» — покажу, что я умею.")

        inbox_item = InboxItem(
            id=uuid4(),
            workspace_id=workspace_id,
            source="telegram",
            raw_content=text,
            parsed_data={"intent": intent.type, "data": intent.data, "chat_id": str(chat_id)},
            status=item_status,
            processed_entity_type=entity_type,
            processed_entity_id=entity_id,
        )
        s.add(inbox_item)
        await publish_event(
            session=s,
            event_type="inbox.item_captured.v1",
            aggregate_type="inbox_item",
            aggregate_id=inbox_item.id,
            workspace_id=workspace_id,
            data={"source": "telegram", "intent": intent.type},
        )
        await s.commit()

        if item_status == "pending":
            from src.integrations.telegram.daily import capture_keyboard

            await send_message(
                chat_id,
                "📥 Сохранил во «Входящие». Что это?",
                reply_markup=capture_keyboard(inbox_item.id),
            )

    if session is not None:
        await _dispatch(session)
    else:
        async with _tenant_session(workspace_id) as s:
            await _dispatch(s)


async def _handle_callback(
    callback_query: Dict[str, Any],
    session: Optional[AsyncSession],
    workspace_id: Optional[UUID],
    integration_id: Optional[UUID],
) -> None:
    cb_id = callback_query.get("id")
    cb_message = callback_query.get("message") or {}
    chat_id = (cb_message.get("chat") or {}).get("id")
    data = callback_query.get("data", "")
    if cb_id:
        await answer_callback(cb_id)
    if not chat_id:
        return

    if data.startswith(("bn:", "bb:", "bc:")):
        if not workspace_id:
            workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session, integration_id=integration_id)
        if not workspace_id:
            await send_message(chat_id, NOT_LINKED_TEXT)
            return
        from src.integrations.telegram import bank_flow

        ws_id = workspace_id

        async def _bank(s: AsyncSession) -> None:
            if data.startswith("bn:"):
                await bank_flow.handle_callback(s, ws_id, chat_id, cb_message.get("message_id"), data)
            else:
                await bank_flow.handle_balance_callback(s, ws_id, chat_id, data)

        try:
            if session is not None:
                await _bank(session)
            else:
                async with _tenant_session(ws_id) as s:
                    await _bank(s)
        except Exception as ex:
            logger.exception("Bank notice callback failed: %s", ex)
            await send_message(chat_id, "Не получилось. Попробуйте ещё раз или запишите операцию в приложении.")
        return

    if data.startswith("iv:"):
        if not workspace_id:
            workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session, integration_id=integration_id)
        if not workspace_id:
            await send_message(chat_id, NOT_LINKED_TEXT)
            return
        from src.integrations.telegram import invites_bot

        await invites_bot.handle_callback(workspace_id, chat_id, cb_message.get("message_id"), data)
        return

    if data.startswith(("in:", "dg:")):
        if not workspace_id:
            workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session, integration_id=integration_id)
        if not workspace_id:
            await send_message(chat_id, NOT_LINKED_TEXT)
            return
        from src.integrations.telegram import daily

        ws_id = workspace_id
        fn = daily.handle_inbox_callback if data.startswith("in:") else daily.handle_digest_callback
        try:
            if session is not None:
                await fn(session, ws_id, chat_id, cb_message.get("message_id"), data)
            else:
                async with _tenant_session(ws_id) as s:
                    await fn(s, ws_id, chat_id, cb_message.get("message_id"), data)
        except Exception as ex:
            logger.exception("Inbox/digest callback failed: %s", ex)
            await send_message(chat_id, "Не получилось. Попробуйте ещё раз.")
        return

    if data.startswith("txu:"):
        if not workspace_id:
            workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session, integration_id=integration_id)
        if not workspace_id:
            await send_message(chat_id, NOT_LINKED_TEXT)
            return
        try:
            tx_id = UUID(data[4:])
        except ValueError:
            return
        ws_id = workspace_id

        async def _undo(s: AsyncSession) -> None:
            try:
                await finance_service.reverse_transaction(s, ws_id, tx_id, reason="Отменено в Telegram")
                await send_message(chat_id, "↩️ Отменено.")
            except Exception:
                await send_message(chat_id, "Эта запись уже отменена или не найдена.")

        if session is not None:
            await _undo(session)
        else:
            async with _tenant_session(ws_id) as s:
                await _undo(s)
        return

    if data == "cancel_expense":
        await send_message(chat_id, "❌ Запись расхода отменена.")
        return
    if not data.startswith("confirm_expense:"):
        return

    _, amount_raw, category = (data.split(":", 2) + ["", ""])[:3]
    try:
        amount = float(amount_raw)
    except ValueError:
        return
    category = category or "прочее"

    if not workspace_id:
        workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session, integration_id=integration_id)
    if not workspace_id:
        await send_message(chat_id, NOT_LINKED_TEXT)
        return

    async def _record(s: AsyncSession) -> None:
        result = await record_expense(s, workspace_id, amount, category)
        if result is None:
            await send_message(chat_id, "Нет счёта для списания. Создайте счёт в приложении (Финансы) и повторите.")
            return
        _tx, account = result[0], result[1]
        await send_message(chat_id, f"✅ Записано: {format_amount(amount)} сум · {category} · {account.name}")

    try:
        if session is not None:
            await _record(session)
        else:
            async with _tenant_session(workspace_id) as s:
                await _record(s)
    except Exception as ex:
        logger.exception("Failed to record Telegram expense: %s", ex)
        await send_message(chat_id, "Не удалось записать расход. Попробуйте ещё раз или добавьте его в приложении.")


class TelegramWebhookHandler:
    """Class adapter for backwards-compatibility."""

    async def handle_update(self, session: AsyncSession, update: Dict[str, Any]) -> Optional[InboxItem]:
        await handle_telegram_update(update, session=session)
        return None


telegram_handler = TelegramWebhookHandler()
