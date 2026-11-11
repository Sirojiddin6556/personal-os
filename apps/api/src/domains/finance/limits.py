"""Monthly spending limit: one overall budget per workspace (Budget with no category).

Set in Telegram ("лимит 5 млн"), shown in the morning/evening digests and the apps,
with a one-time warning when the month reaches 80% and 100% of the limit.
Spending = posted expenses of the current calendar month in the owner's timezone;
transfers (own cards, loans) never count.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.finance.models import Budget, Transaction

LIMIT_NAME = "Общий лимит на месяц"
THRESHOLDS = (80, 100)
OFF_WORDS = {"0", "нет", "выкл", "выключить", "убрать", "удалить", "сбросить", "off"}


def parse_limit_amount(raw: str) -> Optional[int]:
    """'5 млн' / '5000000' / '5 000 000' / '3,5 млн' / '800 тыс' / '800к' -> minor units.

    Returns 0 for "off" words, None when the text is not an amount.
    """
    value = raw.strip().lower().replace("\xa0", " ").replace("сум", "").replace("uzs", "").strip(" .")
    if value in OFF_WORDS:
        return 0
    m = re.fullmatch(r"(\d[\d ]*(?:[.,]\d+)?)\s*(млн|миллион[а-я]*|mln|m|тыс[а-я.]*|k|к)?", value)
    if not m:
        return None
    try:
        number = Decimal(m[1].replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None
    unit = m[2] or ""
    if unit.startswith(("млн", "миллион", "mln")) or unit == "m":
        number *= 1_000_000
    elif unit:
        number *= 1_000
    if number <= 0:
        return 0
    if number > Decimal("1000000000000"):
        return None
    return int(number * 100)


async def get_limit(s: AsyncSession, ws: UUID) -> Optional[Budget]:
    res = await s.execute(
        select(Budget)
        .where(Budget.workspace_id == ws, Budget.category_id.is_(None), Budget.period_type == "monthly")
        .order_by(Budget.created_at)
        .limit(1)
    )
    return res.scalar_one_or_none()


async def set_limit(s: AsyncSession, ws: UUID, amount_minor: int) -> Optional[Budget]:
    """Create/update the limit; 0 removes it. Commits."""
    budget = await get_limit(s, ws)
    if amount_minor <= 0:
        if budget is not None:
            await s.delete(budget)
        await s.commit()
        return None
    if budget is None:
        budget = Budget(workspace_id=ws, category_id=None, name=LIMIT_NAME, amount_minor=amount_minor,
                        currency="UZS", period_type="monthly")
        s.add(budget)
    else:
        budget.amount_minor = amount_minor
    await s.commit()
    return budget


def month_bounds(d: date, tz: ZoneInfo) -> Tuple[datetime, datetime]:
    start = datetime.combine(d.replace(day=1), time(0, 0), tz)
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return start, datetime.combine(nxt, time(0, 0), tz)


async def month_spent(s: AsyncSession, ws: UUID, d: date, tz: ZoneInfo) -> int:
    start, end = month_bounds(d, tz)
    res = await s.execute(
        select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
            Transaction.workspace_id == ws,
            Transaction.transaction_type == "expense",
            Transaction.status == "posted",
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
    )
    return int(res.scalar_one())


@dataclass(frozen=True)
class LimitStatus:
    limit_minor: int
    spent_minor: int
    day: date

    @property
    def percent(self) -> int:
        return int(self.spent_minor * 100 // self.limit_minor) if self.limit_minor else 0

    @property
    def left_minor(self) -> int:
        return self.limit_minor - self.spent_minor

    @property
    def days_left(self) -> int:
        """Days left in the month including today."""
        return calendar.monthrange(self.day.year, self.day.month)[1] - self.day.day + 1

    @property
    def per_day_minor(self) -> int:
        return max(0, self.left_minor) // max(1, self.days_left)


async def status(s: AsyncSession, ws: UUID, d: date, tz: ZoneInfo) -> Tuple[Optional[LimitStatus], int]:
    """(limit status or None when no limit is set, month spending)."""
    spent = await month_spent(s, ws, d, tz)
    budget = await get_limit(s, ws)
    return (LimitStatus(budget.amount_minor, spent, d) if budget else None), spent


def crossed(percent: int, already: list) -> Optional[int]:
    """Highest threshold reached that was not announced yet this month."""
    hit = [t for t in THRESHOLDS if percent >= t and t not in already]
    return max(hit) if hit else None
