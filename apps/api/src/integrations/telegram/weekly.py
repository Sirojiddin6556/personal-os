"""Weekly review in Telegram: Sunday 20:00 (owner's timezone), once a week.

What got done, what is stuck, money of the week vs the week before (and the month
limit), habits, and what the next week holds. One button moves everything overdue
to Monday.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.calendar.models import Event
from src.domains.finance import limits
from src.domains.finance.models import Category, Transaction
from src.domains.planner.models import Habit, HabitLog
from src.domains.tasks.models import Task
from src.integrations.telegram import daily

WINDOW = (time(20, 0), time(23, 59, 59))
SUNDAY = 6


def is_due(now_local: datetime, sent: dict) -> bool:
    return (now_local.weekday() == SUNDAY and WINDOW[0] <= now_local.time() <= WINDOW[1]
            and sent.get("weekly") != now_local.date().isoformat())


def week_bounds(d: date, tz: ZoneInfo) -> Tuple[datetime, datetime]:
    monday = d - timedelta(days=d.weekday())
    start = datetime.combine(monday, time(0, 0), tz)
    return start, start + timedelta(days=7)


@dataclass
class WeekData:
    monday: date
    done: List[str] = field(default_factory=list)
    overdue: List[str] = field(default_factory=list)
    spent: int = 0
    spent_prev: int = 0
    by_category: List[Tuple[str, int]] = field(default_factory=list)
    habits: List[Tuple[str, int]] = field(default_factory=list)  # (title, days done)
    next_events: List[tuple] = field(default_factory=list)
    next_due: int = 0
    day: daily.DayData = field(default_factory=daily.DayData)  # limit, inbox, unsorted transfers


async def _spent(s: AsyncSession, ws: UUID, start: datetime, end: datetime) -> List[Tuple[str, int]]:
    name = func.coalesce(Category.name, "Без категории").label("name")
    total = func.sum(Transaction.amount_minor).label("total")
    res = await s.execute(
        select(name, total)
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.workspace_id == ws, Transaction.transaction_type == "expense",
               Transaction.status == "posted", Transaction.occurred_at >= start, Transaction.occurred_at < end)
        .group_by(name)
        .order_by(total.desc())
    )
    return [(n, int(t)) for n, t in res.all()]


async def collect(s: AsyncSession, ws: UUID, today: date, tz: ZoneInfo) -> WeekData:
    start, end = week_bounds(today, tz)
    data = WeekData(monday=start.date())
    res = await s.execute(
        select(Task.title).where(Task.workspace_id == ws, Task.is_deleted.is_(False), Task.status == "done",
                                 Task.completed_at >= start, Task.completed_at < end)
        .order_by(Task.completed_at)
    )
    data.done = list(res.scalars().all())
    now = datetime.now(tz)
    res = await s.execute(
        select(Task.title).where(Task.workspace_id == ws, Task.is_deleted.is_(False),
                                 Task.status.in_(daily.OPEN_STATUSES), Task.due_at < now)
        .order_by(Task.due_at)
    )
    data.overdue = list(res.scalars().all())

    data.by_category = await _spent(s, ws, start, end)
    data.spent = sum(v for _, v in data.by_category)
    data.spent_prev = sum(v for _, v in await _spent(s, ws, start - timedelta(days=7), start))

    res = await s.execute(
        select(Habit.title, func.count(HabitLog.id))
        .select_from(Habit)
        .outerjoin(HabitLog, (HabitLog.habit_id == Habit.id) & (HabitLog.logged_date >= start.date())
                   & (HabitLog.logged_date < end.date()))
        .where(Habit.workspace_id == ws, Habit.is_archived.is_(False))
        .group_by(Habit.id, Habit.title)
        .order_by(Habit.title)
    )
    data.habits = [(t, int(n)) for t, n in res.all()]

    res = await s.execute(
        select(Event.starts_at, Event.ends_at, Event.is_all_day, Event.title)
        .where(Event.workspace_id == ws, Event.status != "cancelled",
               Event.starts_at >= end, Event.starts_at < end + timedelta(days=7))
        .order_by(Event.starts_at)
    )
    data.next_events = [tuple(r) for r in res.all()]
    data.next_due = (await s.execute(
        select(func.count()).select_from(Task).where(
            Task.workspace_id == ws, Task.is_deleted.is_(False), Task.status.in_(daily.OPEN_STATUSES),
            Task.due_at >= end, Task.due_at < end + timedelta(days=7))
    )).scalar_one()

    data.day = await daily.collect(s, ws, today, tz, spending_day=today)
    return data


WEEKDAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def _event_line(ev, tz: ZoneInfo) -> str:
    starts, _ends, all_day, title = ev
    local = starts.astimezone(tz)
    when = f"{WEEKDAYS_SHORT[local.weekday()]} {local.day:02d}.{local.month:02d}"
    return f"• {when}{'' if all_day else local.strftime(' %H:%M')} — {title}"


def weekly_text(w: WeekData, tz: ZoneInfo) -> str:
    sunday = w.monday + timedelta(days=6)
    out = [f"📆 Итоги недели · {w.monday.day} {daily.MONTHS[w.monday.month - 1]} — "
           f"{sunday.day} {daily.MONTHS[sunday.month - 1]}", ""]

    out.append(f"✅ Сделано задач: {len(w.done)}" if w.done else "✅ Закрытых задач на этой неделе нет")
    out += daily._clip([f"• {t}" for t in w.done])
    if w.overdue:
        out.append(f"⚠️ Просрочено сейчас: {len(w.overdue)}")
        out += daily._clip([f"• {t}" for t in w.overdue])
    out.append("")

    if w.spent:
        line = f"💳 Потрачено за неделю: {daily.money(w.spent)}"
        if w.spent_prev:
            diff = round((w.spent - w.spent_prev) * 100 / w.spent_prev)
            line += f" ({'+' if diff > 0 else ''}{diff}% к прошлой: {daily.money(w.spent_prev)})"
        out.append(line)
        out += [f"  {name} — {daily.money(v)}" for name, v in w.by_category[:5]]
    else:
        out.append("💳 Трат за неделю нет" + (f" (прошлая: {daily.money(w.spent_prev)})" if w.spent_prev else ""))
    out += daily.limit_lines(w.day, hint=True)

    if w.habits:
        out += ["", "🔁 Привычки:"] + [f"• {t}: {n} из 7" for t, n in w.habits]

    out += ["", f"📅 Следующая неделя: событий {len(w.next_events)}, задач со сроком {w.next_due}"]
    out += daily._clip([_event_line(e, tz) for e in w.next_events])
    if w.day.inbox_pending:
        out.append(f"📥 Во «Входящих» не разобрано: {w.day.inbox_pending}")
    return "\n".join(out).strip()


def keyboard(w: WeekData, today: date) -> Optional[dict]:
    rows = []
    if w.overdue:
        rows.append([{"text": "➡️ Просроченное — на понедельник", "callback_data": f"dg:carry:{today:%Y%m%d}"}])
    if w.day.p2p_unsorted:
        rows.append([{"text": f"🔁 Разобрать переводы ({w.day.p2p_unsorted})", "callback_data": "dg:p2p"}])
    app = daily.app_button()
    if app:
        rows.append(app)
    return {"inline_keyboard": rows} if rows else None
