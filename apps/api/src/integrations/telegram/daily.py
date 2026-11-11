"""Daily loop in Telegram: the system comes to the user instead of waiting to be opened.

- 08:00 morning brief: today's events, tasks due / overdue, unsorted inbox, yesterday's spending
- 21:00 evening summary: today's spending, tasks done, what is left (one tap: move to tomorrow)
- 15 minutes before a calendar event: a reminder
- Any message the bot did not understand lands in the inbox with buttons to sort it

Times are in the workspace owner's timezone. A digest missed while the server was down is
still sent within its window (morning until 11:00, evening until midnight), never twice.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import async_session_factory
from src.domains.calendar.models import Event
from src.domains.finance import limits
from src.domains.finance.models import Category, Transaction
from src.domains.identity.models import User, Workspace
from src.domains.tasks.models import Task
from src.integrations.models import InboxItem, Integration

logger = logging.getLogger("personal_os.daily")

MORNING = (time(8, 0), time(11, 0))
EVENING = (time(21, 0), time(23, 59, 59))
EVENT_LEAD = timedelta(minutes=15)
OPEN_STATUSES = ("inbox", "todo", "scheduled", "in_progress", "waiting")
WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]
MAX_LINES = 7


def money(minor: int) -> str:
    return f"{round(minor / 100):,}".replace(",", " ") + " сум"


def day_title(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]}"


def due_digests(now_local: datetime, sent: Dict[str, str]) -> List[str]:
    """Which digests are due now (inside their window and not yet sent today)."""
    today = now_local.date().isoformat()
    due = []
    for kind, (start, end) in (("morning", MORNING), ("evening", EVENING)):
        if start <= now_local.time() <= end and sent.get(kind) != today:
            due.append(kind)
    from src.integrations.telegram import weekly

    if weekly.is_due(now_local, sent):
        due.append("weekly")
    return due


def _clip(lines: Sequence[str]) -> List[str]:
    lines = list(lines)
    if len(lines) > MAX_LINES:
        return lines[:MAX_LINES] + [f"  …и ещё {len(lines) - MAX_LINES}"]
    return lines


# ------------------------------------------------------------------ data
@dataclass
class DayData:
    events: List[Tuple[datetime, Optional[datetime], bool, str]] = field(default_factory=list)
    due_today: List[str] = field(default_factory=list)
    overdue: List[str] = field(default_factory=list)
    done_today: List[str] = field(default_factory=list)
    inbox_pending: int = 0
    spent_minor: int = 0
    spent_by_category: List[Tuple[str, int]] = field(default_factory=list)
    spent_count: int = 0
    month_spent: int = 0
    limit: Optional[limits.LimitStatus] = None
    p2p_unsorted: int = 0
    p2p_unsorted_minor: int = 0


def _day_bounds(d: date, tz: ZoneInfo) -> Tuple[datetime, datetime]:
    start = datetime.combine(d, time(0, 0), tz)
    return start, start + timedelta(days=1)


async def _events(s: AsyncSession, ws: UUID, d: date, tz: ZoneInfo):
    start, end = _day_bounds(d, tz)
    res = await s.execute(
        select(Event.starts_at, Event.ends_at, Event.is_all_day, Event.title)
        .where(Event.workspace_id == ws, Event.status != "cancelled",
               Event.starts_at < end, Event.ends_at > start)
        .order_by(Event.is_all_day.desc(), Event.starts_at)
    )
    return [tuple(r) for r in res.all()]


async def _spending(s: AsyncSession, ws: UUID, d: date, tz: ZoneInfo):
    start, end = _day_bounds(d, tz)
    name = func.coalesce(Category.name, "Без категории").label("name")
    total = func.sum(Transaction.amount_minor).label("total")
    res = await s.execute(
        select(name, total, func.count())
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.workspace_id == ws, Transaction.transaction_type == "expense",
               Transaction.status == "posted", Transaction.occurred_at >= start, Transaction.occurred_at < end)
        .group_by(name)
        .order_by(total.desc())
    )
    rows = [(name, int(total), int(n)) for name, total, n in res.all()]
    return sum(r[1] for r in rows), [(r[0], r[1]) for r in rows], sum(r[2] for r in rows)


async def collect(s: AsyncSession, ws: UUID, d: date, tz: ZoneInfo, spending_day: date) -> DayData:
    data = DayData()
    data.events = await _events(s, ws, d, tz)
    start, end = _day_bounds(d, tz)
    open_task = (Task.workspace_id == ws, Task.is_deleted.is_(False), Task.status.in_(OPEN_STATUSES))
    res = await s.execute(select(Task.title, Task.due_at).where(*open_task, Task.due_at < end).order_by(Task.due_at))
    for title, due in res.all():
        (data.overdue if due < start else data.due_today).append(title)
    res = await s.execute(
        select(Task.title).where(Task.workspace_id == ws, Task.is_deleted.is_(False), Task.status == "done",
                                 Task.completed_at >= start, Task.completed_at < end)
    )
    data.done_today = list(res.scalars().all())
    data.inbox_pending = (await s.execute(
        select(func.count()).select_from(InboxItem).where(InboxItem.workspace_id == ws, InboxItem.status == "pending")
    )).scalar_one()
    data.spent_minor, data.spent_by_category, data.spent_count = await _spending(s, ws, spending_day, tz)
    data.limit, data.month_spent = await limits.status(s, ws, d, tz)
    from src.integrations.telegram.bank_flow import unsorted_p2p

    month_start, _ = limits.month_bounds(d, tz)
    p2p = await unsorted_p2p(s, ws, month_start)
    data.p2p_unsorted, data.p2p_unsorted_minor = len(p2p), sum(n.amount_minor for n in p2p)
    return data


# ------------------------------------------------------------------ texts
def _event_line(ev, tz: ZoneInfo) -> str:
    starts, ends, all_day, title = ev
    if all_day:
        return f"• весь день — {title}"
    a = starts.astimezone(tz).strftime("%H:%M")
    b = ends.astimezone(tz).strftime("%H:%M") if ends else ""
    return f"• {a}{'–' + b if b else ''} {title}"


def _spending_block(header: str, data: DayData) -> List[str]:
    if not data.spent_minor:
        return [f"{header}: ничего"]
    top = ", ".join(f"{name} {money(v)}" for name, v in data.spent_by_category[:3])
    return [f"{header}: {money(data.spent_minor)} ({data.spent_count} опер.)", f"  {top}"]


def limit_lines(data: DayData, hint: bool = False) -> List[str]:
    """Month spending against the limit; a short hint how to set one when there is none."""
    out: List[str] = []
    lim = data.limit
    if lim is not None:
        icon = "🟥" if lim.percent >= 100 else "🟨" if lim.percent >= 80 else "🟩"
        out.append(f"{icon} Месяц: {money(lim.spent_minor)} из {money(lim.limit_minor)} ({lim.percent}%)")
        if lim.left_minor > 0:
            out.append(f"  Осталось {money(lim.left_minor)} — по {money(lim.per_day_minor)} в день "
                       f"({lim.days_left} дн.)")
        else:
            out.append(f"  Лимит превышен на {money(-lim.left_minor)}")
    elif data.month_spent:
        out.append(f"📊 За месяц потрачено: {money(data.month_spent)}")
        if hint:
            out.append("  Задать лимит: напишите «лимит 5 млн»")
    if data.p2p_unsorted:
        out.append(f"🔁 Переводы без пометки: {data.p2p_unsorted} на {money(data.p2p_unsorted_minor)} — "
                   "сейчас считаются расходом")
    return out


def limit_alert_text(lim: limits.LimitStatus, threshold: int) -> str:
    if threshold >= 100:
        return (f"🟥 Месячный лимит исчерпан: потрачено {money(lim.spent_minor)} из {money(lim.limit_minor)}"
                + (f" (сверх лимита {money(-lim.left_minor)})." if lim.left_minor < 0 else "."))
    return (f"🟨 Потрачено {lim.percent}% месячного лимита: {money(lim.spent_minor)} из {money(lim.limit_minor)}.\n"
            f"До конца месяца {lim.days_left} дн. — можно по {money(lim.per_day_minor)} в день.")


def morning_text(d: date, data: DayData, tz: ZoneInfo) -> str:
    out = [f"☀️ Доброе утро! {day_title(d)}", ""]
    out.append("📅 Сегодня:" if data.events else "📅 Событий в календаре нет")
    out += _clip([_event_line(e, tz) for e in data.events])
    out.append("")
    if data.overdue:
        out.append(f"⚠️ Просрочено ({len(data.overdue)}):")
        out += _clip([f"• {t}" for t in data.overdue])
    if data.due_today:
        out.append(f"✅ Задачи на сегодня ({len(data.due_today)}):")
        out += _clip([f"• {t}" for t in data.due_today])
    if not data.overdue and not data.due_today:
        out.append("✅ Задач со сроком на сегодня нет")
    if data.inbox_pending:
        out.append(f"📥 Во «Входящих» не разобрано: {data.inbox_pending}")
    out.append("")
    out += _spending_block("💳 Вчера потрачено", data)
    out += limit_lines(data)
    return "\n".join(out).strip()


def evening_text(d: date, data: DayData, tomorrow: List, tz: ZoneInfo) -> str:
    out = [f"🌙 Итоги дня — {day_title(d)}", ""]
    out += _spending_block("💳 Потрачено сегодня", data)
    out += limit_lines(data, hint=True)
    out.append("")
    if data.done_today:
        out.append(f"✅ Сделано ({len(data.done_today)}):")
        out += _clip([f"• {t}" for t in data.done_today])
    left = data.overdue + data.due_today
    if left:
        out.append(f"⏳ Не сделано ({len(left)}):")
        out += _clip([f"• {t}" for t in left])
    if not data.done_today and not left:
        out.append("Задач со сроком на сегодня не было")
    if data.inbox_pending:
        out.append(f"📥 Во «Входящих» не разобрано: {data.inbox_pending}")
    if tomorrow:
        out += ["", "📅 Завтра:"] + _clip([_event_line(e, tz) for e in tomorrow])
    return "\n".join(out).strip()


def app_button() -> List[Dict[str, Any]]:
    url = (settings.telegram_miniapp_url or "").strip()
    return [{"text": "📱 Открыть приложение", "web_app": {"url": url}}] if url.startswith("https://") else []


# ------------------------------------------------------------------ inbox capture
def capture_keyboard(item_id: UUID) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "✅ Задача", "callback_data": f"in:t:{item_id}"},
         {"text": "⏰ Напомнить", "callback_data": f"in:r:{item_id}"}],
        [{"text": "📝 Заметка", "callback_data": f"in:n:{item_id}"},
         {"text": "🗑 Удалить", "callback_data": f"in:d:{item_id}"}],
    ]}


async def handle_inbox_callback(s: AsyncSession, ws: UUID, chat_id: Any, message_id: Optional[int], data: str) -> None:
    from src.domains.knowledge.schemas import NoteCreate
    from src.domains.knowledge.service import knowledge_service
    from src.domains.planner.schemas import PlannerReminderCreate
    from src.domains.planner.service import planner_service
    from src.domains.tasks.schemas import TaskCreate
    from src.domains.tasks.service import task_service
    from src.integrations.telegram.handler import REMINDER_TZ, edit_message, parse_reminder, send_message

    parts = data.split(":")
    if len(parts) != 3:
        return
    try:
        item_id = UUID(parts[2])
    except ValueError:
        return
    item = (await s.execute(
        select(InboxItem).where(InboxItem.id == item_id, InboxItem.workspace_id == ws).with_for_update()
    )).scalar_one_or_none()
    if item is None or item.status != "pending":
        await send_message(chat_id, "Эта запись уже разобрана.")
        return
    text = item.raw_content.strip()
    action = parts[1]

    if action == "t":
        task = await task_service.create(s, ws, TaskCreate(title=text[:500]))
        item.status, item.processed_entity_type, item.processed_entity_id = "processed", "task", task.id
        reply = f"✅ Задача: {task.title}"
    elif action == "r":
        title, remind_at = parse_reminder(text)
        rem = await planner_service.create_reminder(s, ws, PlannerReminderCreate(title=title, remind_at=remind_at))
        item.status, item.processed_entity_type, item.processed_entity_id = "processed", "reminder", rem.id
        reply = f"⏰ Напомню {remind_at.astimezone(REMINDER_TZ):%d.%m в %H:%M}: {rem.title}"
    elif action == "n":
        first = text.splitlines()[0][:80] or "Заметка"
        note = await knowledge_service.create_note(s, ws, NoteCreate(title=first, content_markdown=text))
        item.status, item.processed_entity_type, item.processed_entity_id = "processed", "note", note.id
        reply = f"📝 Заметка: {first}"
    elif action == "d":
        item.status = "discarded"
        reply = f"🗑 Удалено: {text[:80]}"
    else:
        return
    await s.commit()
    if message_id:
        await edit_message(chat_id, message_id, reply)
    else:
        await send_message(chat_id, reply)


# ------------------------------------------------------------------ "move to tomorrow"
async def handle_digest_callback(s: AsyncSession, ws: UUID, chat_id: Any, message_id: Optional[int], data: str) -> None:
    from src.integrations.telegram.handler import send_message

    if data == "dg:p2p":
        from src.integrations.telegram.bank_flow import ask_unsorted_p2p

        tz = await owner_tz(s, ws)
        since, _ = limits.month_bounds(datetime.now(tz).date(), tz)
        await ask_unsorted_p2p(s, ws, chat_id, since)
        return
    if not data.startswith("dg:carry:"):
        return
    tz = await owner_tz(s, ws)
    try:
        d = datetime.strptime(data[9:], "%Y%m%d").date()
    except ValueError:
        return
    _, end = _day_bounds(d, tz)
    res = await s.execute(
        select(Task).where(Task.workspace_id == ws, Task.is_deleted.is_(False),
                           Task.status.in_(OPEN_STATUSES), Task.due_at < end)
    )
    tasks = list(res.scalars().all())
    tomorrow_9 = datetime.combine(d + timedelta(days=1), time(9, 0), tz)
    for t in tasks:
        local = t.due_at.astimezone(tz)
        t.due_at = datetime.combine(tomorrow_9.date(), local.time(), tz) if local.date() == d else tomorrow_9
        t.version += 1
    await s.commit()
    await send_message(chat_id, f"➡️ Перенёс на завтра: {len(tasks)}" if tasks else "Переносить нечего.")


# ------------------------------------------------------------------ loop
async def owner_tz(s: AsyncSession, ws: UUID) -> ZoneInfo:
    name = (await s.execute(
        select(User.timezone).join(Workspace, Workspace.owner_id == User.id).where(Workspace.id == ws)
    )).scalar_one_or_none()
    try:
        return ZoneInfo(name or settings.default_timezone)
    except Exception:
        return ZoneInfo(settings.default_timezone)


class _Seen:
    """Event reminders already sent: Redis (survives restarts) with an in-memory fallback."""

    def __init__(self) -> None:
        self.memory: Dict[str, datetime] = {}
        self.redis = None

    async def first_time(self, key: str, ttl: int = 7200) -> bool:
        try:
            if self.redis is None:
                import redis.asyncio as aioredis

                self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            return bool(await self.redis.set(f"pos:evremind:{key}", "1", nx=True, ex=ttl))
        except Exception:
            now = datetime.now(timezone.utc)
            self.memory = {k: v for k, v in self.memory.items() if v > now}
            if key in self.memory:
                return False
            self.memory[key] = now + timedelta(seconds=ttl)
            return True


async def send_digest(s: AsyncSession, integ: Integration, kind: str, now_local: datetime, tz: ZoneInfo,
                      chat: str, token: Optional[str]) -> None:
    from src.integrations.telegram.handler import send_message

    today = now_local.date()
    ws = integ.workspace_id
    if kind == "weekly":
        from src.integrations.telegram import weekly

        w = await weekly.collect(s, ws, today, tz)
        await send_message(chat, weekly.weekly_text(w, tz), reply_markup=weekly.keyboard(w, today), bot_token=token)
        return
    if kind == "morning":
        data = await collect(s, ws, today, tz, spending_day=today - timedelta(days=1))
        text, rows = morning_text(today, data, tz), [app_button()]
    else:
        data = await collect(s, ws, today, tz, spending_day=today)
        tomorrow = await _events(s, ws, today + timedelta(days=1), tz)
        text = evening_text(today, data, tomorrow, tz)
        carry = ([{"text": "➡️ Перенести несделанное на завтра", "callback_data": f"dg:carry:{today:%Y%m%d}"}]
                 if data.overdue or data.due_today else [])
        rows = [carry, app_button()]
    if data.p2p_unsorted:
        rows.insert(0, [{"text": f"🔁 Разобрать переводы ({data.p2p_unsorted})", "callback_data": "dg:p2p"}])
    rows = [r for r in rows if r]
    await send_message(chat, text, reply_markup={"inline_keyboard": rows} if rows else None, bot_token=token)


def mark_limit_announced(integ: Integration, month: str, percent: int, reset: bool = False) -> None:
    """Remember thresholds already reached this month. ``reset`` (a new limit was set):
    forget earlier warnings and count only what the current spending already reached,
    so the user is not warned about what the reply just told them."""
    cfg = dict(integ.config or {})
    alerts = dict(cfg.get("limit_alerts") or {})
    done = [] if reset else [t for t in alerts.get(month, []) if t in limits.THRESHOLDS]
    done += [t for t in limits.THRESHOLDS if percent >= t and t not in done]
    cfg["limit_alerts"] = {month: sorted(done)}  # older months are dropped
    integ.config = cfg


LIMIT_RE = re.compile(r"^(?:лимит|limit|бюджет)(?!\w)(?:\s+на\s+месяц)?\s*[:=]?\s*(.*)$", re.I)


async def handle_limit_command(s: AsyncSession, ws: UUID, chat_id: Any, arg: str) -> None:
    """"лимит" shows the month, "лимит 5 млн" sets it, "лимит 0"/"лимит выкл" removes it."""
    from src.integrations.telegram.handler import send_message

    tz = await owner_tz(s, ws)
    today = datetime.now(tz).date()
    arg = arg.strip()
    if arg:
        amount = limits.parse_limit_amount(arg)
        if amount is None:
            await send_message(chat_id, "Не понял сумму. Примеры: «лимит 5 млн», «лимит 3 500 000», «лимит выкл».")
            return
        await limits.set_limit(s, ws, amount)
    lim, spent = await limits.status(s, ws, today, tz)
    if lim is None:
        text = ("Лимит убран." if arg else "Месячный лимит не задан. Напишите, например, «лимит 5 млн».") + (
            f"\nЗа этот месяц потрачено: {money(spent)}" if spent else "")
        await send_message(chat_id, text)
        return
    integ = (await s.execute(
        select(Integration).where(Integration.workspace_id == ws, Integration.provider == "telegram")
    )).scalars().first()
    if arg and integ is not None:
        mark_limit_announced(integ, today.strftime("%Y-%m"), lim.percent, reset=True)
        await s.commit()
    data = DayData(month_spent=spent, limit=lim)
    head = f"✅ Лимит на месяц: {money(lim.limit_minor)}" if arg else f"Лимит на месяц: {money(lim.limit_minor)}"
    await send_message(chat_id, "\n".join([head] + limit_lines(data)
                                          + ["", "Предупрежу, когда потратите 80% и 100%. Изменить: «лимит 6 млн», убрать: «лимит выкл»."]))


async def check_limit(s: AsyncSession, integ: Integration, now_local: datetime, tz: ZoneInfo,
                      chat: str, token: Optional[str]) -> None:
    from src.integrations.telegram.handler import send_message

    lim, _ = await limits.status(s, integ.workspace_id, now_local.date(), tz)
    if lim is None:
        return
    month = now_local.strftime("%Y-%m")
    already = list(((integ.config or {}).get("limit_alerts") or {}).get(month, []))
    threshold = limits.crossed(lim.percent, already)
    if threshold is None:
        return
    await send_message(chat, limit_alert_text(lim, threshold), bot_token=token)
    mark_limit_announced(integ, month, lim.percent)
    await s.commit()


async def tick(now: Optional[datetime] = None, seen: Optional[_Seen] = None) -> None:
    from src.integrations.telegram.handler import send_message
    from src.integrations.telegram.reminders import _chat_and_token

    now = now or datetime.now(timezone.utc)
    async with async_session_factory() as s:
        res = await s.execute(
            select(Integration).where(Integration.provider == "telegram", Integration.status == "connected")
        )
        for integ in res.scalars().all():
            chat, token = _chat_and_token(integ)
            if not chat:
                continue
            ws = integ.workspace_id
            tz = await owner_tz(s, ws)
            now_local = now.astimezone(tz)
            cfg = dict(integ.config or {})
            sent = dict(cfg.get("digests_sent") or {})
            for kind in due_digests(now_local, sent):
                try:
                    await send_digest(s, integ, kind, now_local, tz, chat, token)
                except Exception as ex:
                    logger.warning("%s digest for workspace %s failed: %s", kind, ws, ex)
                    continue
                sent[kind] = now_local.date().isoformat()
                cfg["digests_sent"] = sent
                integ.config = cfg
                await s.commit()

            try:
                await check_limit(s, integ, now_local, tz, chat, token)
            except Exception as ex:
                logger.warning("Limit check for workspace %s failed: %s", ws, ex)

            if seen is None:
                continue
            res_ev = await s.execute(
                select(Event.id, Event.starts_at, Event.ends_at, Event.title, Event.location)
                .where(Event.workspace_id == ws, Event.status != "cancelled", Event.is_all_day.is_(False),
                       Event.starts_at > now, Event.starts_at <= now + EVENT_LEAD)
            )
            for ev_id, starts, ends, title, location in res_ev.all():
                if not await seen.first_time(f"{ev_id}:{int(starts.timestamp())}"):
                    continue
                minutes = max(1, round((starts - now).total_seconds() / 60))
                line = f"🔔 Через {minutes} мин: {title}\n🕒 {starts.astimezone(tz):%H:%M}–{ends.astimezone(tz):%H:%M}"
                if location:
                    line += f"\n📍 {location}"
                try:
                    await send_message(chat, line, bot_token=token)
                except Exception as ex:
                    logger.warning("Event reminder %s not delivered: %s", ev_id, ex)


class DailyLoop:
    def __init__(self, interval: float = 60.0):
        self.interval = interval
        self.seen = _Seen()
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Daily Telegram loop started (digests 08:00/21:00, weekly Sun 20:00, event reminders).")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        await asyncio.sleep(20)
        while True:
            try:
                await tick(seen=self.seen)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logger.warning("Daily loop tick failed: %s", ex)
            await asyncio.sleep(self.interval)


daily_loop = DailyLoop()
