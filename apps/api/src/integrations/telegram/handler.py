"""Telegram update handler: AI/Rule-based intent classification and command dispatch."""

import json
import logging
import re
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import async_session_factory, set_tenant_context
from src.domains.notifications.service import notification_service
from src.domains.tasks.schemas import TaskCreate
from src.domains.tasks.service import task_service
from src.integrations.models import InboxItem, Integration
from src.shared.outbox import publish_event

logger = logging.getLogger(__name__)


class TelegramIntent:
    """Classified intent result from natural language message."""

    def __init__(self, intent_type: str, data: Dict[str, Any], confidence: float = 1.0):
        self.type = intent_type
        self.data = data
        self.confidence = confidence

    def __repr__(self) -> str:
        return f"TelegramIntent(type={self.type!r}, data={self.data!r})"


def confirm_keyboard(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Telegram inline keyboard for mutating expense confirmations."""
    amount = data.get("amount", 0)
    category = data.get("category", "разное")
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Подтвердить",
                    "callback_data": f"confirm_expense:{amount}:{category}",
                },
                {
                    "text": "❌ Отмена",
                    "callback_data": "cancel_expense",
                },
            ]
        ]
    }


async def send_message(
    chat_id: int | str,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send message to Telegram chat via Bot API."""
    if (
        not settings.telegram_bot_token
        or settings.telegram_bot_token.startswith("mock-")
        or settings.telegram_bot_token in ("test", "dev")
    ):
        logger.info("[Mock Telegram Send] Chat %s: %s | Markup: %s", chat_id, text, reply_markup)
        return {
            "ok": True,
            "result": {
                "message_id": 99999,
                "chat": {"id": chat_id},
                "text": text,
            },
        }

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_workspace_by_telegram_chat(
    chat_id: int | str,
    session: Optional[AsyncSession] = None,
) -> Optional[UUID]:
    """Resolve tenant workspace_id linked to given Telegram chat ID."""
    chat_str = str(chat_id)

    async def _query(s: AsyncSession) -> Optional[UUID]:
        stmt = select(Integration).where(
            Integration.provider == "telegram",
            Integration.status == "connected",
        )
        res = await s.execute(stmt)
        integrations = res.scalars().all()

        for integ in integrations:
            if str(integ.config.get("chat_id")) == chat_str:
                return integ.workspace_id

        # If chat_id not explicitly configured yet, fallback to single workspace integration
        if len(integrations) == 1:
            return integrations[0].workspace_id

        return None

    if session is not None:
        return await _query(session)

    async with async_session_factory() as s:
        return await _query(s)


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

    # Direct expense pattern: "500 руб такси", "350р обед"
    direct_expense = re.match(
        r"^(\d+(?:[\.,]\d+)?)\s*(?:руб|рублей|р|₽)\s*(?:на|в|за)?\s*(.*)$",
        lower_text,
    )
    if direct_expense:
        amount_raw = direct_expense.group(1).replace(",", ".")
        amount = float(amount_raw)
        category = direct_expense.group(2).strip() or "прочее"
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
) -> None:
    """Process incoming Telegram update and execute matched domain action."""
    # 1. Handle Inline Keyboard Callback Queries (e.g. Confirm Expense)
    callback_query = update.get("callback_query")
    if callback_query:
        cb_chat_id = callback_query["message"]["chat"]["id"]
        cb_data = callback_query.get("data", "")
        if cb_data.startswith("confirm_expense:"):
            parts = cb_data.split(":")
            amount = parts[1] if len(parts) > 1 else "0"
            category = parts[2] if len(parts) > 2 else "расход"
            await send_message(cb_chat_id, f"✅ Расход {amount} руб. на «{category}» подтвержден и записан.")
        elif cb_data == "cancel_expense":
            await send_message(cb_chat_id, "❌ Запись расхода отменена.")
        return

    # 2. Extract Message details
    message = update.get("message") or update.get("edited_message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id or not text:
        return

    if not workspace_id:
        workspace_id = await get_workspace_by_telegram_chat(chat_id, session=session)

    # 3. Handle /start onboarding command
    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            try:
                target_wid = UUID(parts[1])
                # Link chat to workspace
                async def _link(s: AsyncSession) -> None:
                    stmt = select(Integration).where(
                        Integration.workspace_id == target_wid,
                        Integration.provider == "telegram",
                    )
                    res = await s.execute(stmt)
                    integ = res.scalar_one_or_none()
                    if not integ:
                        integ = Integration(
                            id=uuid4(),
                            workspace_id=target_wid,
                            provider="telegram",
                            status="connected",
                            config={"chat_id": str(chat_id)},
                        )
                        s.add(integ)
                    else:
                        integ.config = {**integ.config, "chat_id": str(chat_id)}
                        integ.status = "connected"
                    await s.commit()

                if session:
                    await _link(session)
                else:
                    async with async_session_factory() as s:
                        await _link(s)

                await send_message(chat_id, "✅ Telegram успешно привязан к Personal OS!")
                return
            except Exception as ex:
                logger.warning("Could not link telegram with token: %s", ex)

        if not workspace_id:
            await send_message(
                chat_id,
                "Привяжите аккаунт. Отправьте /start в приложении.",
            )
            return

    if not workspace_id:
        await send_message(
            chat_id,
            "Привяжите аккаунт. Отправьте /start в приложении.",
        )
        return

    # 4. Dispatch Intent using Session
    async def _dispatch(s: AsyncSession) -> None:
        intent = await ai_parse_telegram_message(text, workspace_id)

        match intent.type:
            case "GREETING":
                welcome_text = (
                    "👋 Привет! Я ваш персональный ассистент Personal OS.\n\n"
                    "Я помогу быстро фиксировать задачи и финансы:\n\n"
                    "📋 Создание задач:\n"
                    "• Задача: Купить билеты\n"
                    "• Сделать: Подготовить презентацию\n"
                    "• todo: Deploy release\n\n"
                    "💳 Учёт расходов:\n"
                    "• Расход: 500 руб кафе\n"
                    "• Потратил 1500 руб супермаркет\n"
                    "• 350р такси\n\n"
                    "⏰ Напоминания:\n"
                    "• Напоминание: в 18:00 созвон\n"
                    "• Напомни выпить витамины\n\n"
                    "Просто напишите мне задачу или сумму расхода!"
                )
                await send_message(chat_id, welcome_text)

            case "CREATE_TASK":
                task_data = TaskCreate(**intent.data) if isinstance(intent.data, dict) else intent.data
                task = await task_service.create(s, workspace_id, task_data)
                await send_message(chat_id, f"✅ Задача создана: {task.title}")

            case "CREATE_EXPENSE":
                keyboard = confirm_keyboard(intent.data)
                await send_message(
                    chat_id,
                    f'Расход {intent.data["amount"]} руб. на "{intent.data["category"]}"?',
                    reply_markup=keyboard,
                )

            case "CREATE_REMINDER":
                reminder = await notification_service.create_reminder(s, workspace_id, intent.data)
                await send_message(chat_id, f"⏰ Напоминание установлено: {reminder.title}")

            case _:
                await send_message(
                    chat_id,
                    "Не понял команду. Попробуйте: «Задача: ...» или «Расход: 500 руб кафе»",
                )

        # Log to inbox_items
        entity_type: Optional[str] = None
        entity_id: Optional[UUID] = None
        item_status = "pending"

        if intent.type == "CREATE_TASK" and 'task' in locals() and task:
            entity_type = "task"
            entity_id = task.id
            item_status = "processed"
        elif intent.type == "CREATE_REMINDER" and 'reminder' in locals() and reminder:
            entity_type = "reminder"
            entity_id = reminder.id
            item_status = "processed"

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

    if session is not None:
        await _dispatch(session)
    else:
        async with async_session_factory() as s:
            async with s.begin():
                await set_tenant_context(s, workspace_id)
                await _dispatch(s)


class TelegramWebhookHandler:
    """Class adapter for backwards-compatibility."""

    async def handle_update(self, session: AsyncSession, update: Dict[str, Any]) -> Optional[InboxItem]:
        await handle_telegram_update(update, session=session)
        return None


telegram_handler = TelegramWebhookHandler()
