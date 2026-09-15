"""Dashboard aggregation service pulling cross-domain metrics."""

from datetime import datetime, time, timezone
from typing import List, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.calendar.models import Event
from src.domains.calendar.schemas import EventResponse
from src.domains.dashboard.schemas import (
    BudgetSummary,
    DashboardStats,
    DashboardSummaryResponse,
    DashboardToday,
    HabitSummary,
    TimeWindow,
)
from src.domains.finance.models import Account, Transaction
from src.domains.notifications.models import Notification
from src.domains.planner.models import Habit, HabitLog
from src.domains.tasks.models import Task
from src.domains.tasks.schemas import TaskResponse


def get_day_bounds(user_tz: str) -> Tuple[datetime, datetime]:
    """Compute start and end datetimes of today in the user's timezone."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = timezone.utc

    now_tz = datetime.now(tz)
    today_start = datetime.combine(now_tz.date(), time.min).replace(tzinfo=tz)
    today_end = datetime.combine(now_tz.date(), time.max).replace(tzinfo=tz)
    return today_start, today_end


async def get_events_today(
    session: AsyncSession,
    workspace_id: UUID,
    today_start: datetime,
    today_end: datetime,
) -> List[EventResponse]:
    """Retrieve today's non-cancelled calendar events within the time bounds."""
    stmt = (
        select(Event)
        .where(
            Event.workspace_id == workspace_id,
            Event.status != "cancelled",
            Event.ends_at >= today_start,
            Event.starts_at <= today_end,
        )
        .order_by(Event.starts_at.asc())
    )
    res = await session.execute(stmt)
    return [EventResponse.model_validate(e) for e in res.scalars().all()]


async def get_top_tasks(
    session: AsyncSession,
    workspace_id: UUID,
    limit: int = 3,
) -> List[TaskResponse]:
    """Retrieve top active tasks ordered by priority and due date."""
    stmt = (
        select(Task)
        .where(
            Task.workspace_id == workspace_id,
            Task.is_deleted.is_(False),
            Task.status.notin_(["done", "cancelled", "archived"]),
        )
        .order_by(Task.due_at.asc().nulls_last(), Task.rank.asc(), Task.created_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return [TaskResponse.model_validate(t) for t in res.scalars().all()]


async def count_overdue(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Count number of incomplete tasks whose due date is in the past."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(func.count(Task.id))
        .where(
            Task.workspace_id == workspace_id,
            Task.is_deleted.is_(False),
            Task.status.notin_(["done", "cancelled", "archived"]),
            Task.due_at < now,
        )
    )
    res = await session.execute(stmt)
    return res.scalar_one() or 0


def calculate_free_windows(
    events: List[EventResponse],
    today_start: datetime,
    today_end: datetime,
) -> List[TimeWindow]:
    """Identify contiguous unbooked time slots (>= 15 min) between today's events."""
    free_windows: List[TimeWindow] = []
    sorted_events = sorted(events, key=lambda e: e.starts_at)
    current_time = today_start

    for ev in sorted_events:
        ev_start = max(ev.starts_at, today_start)
        ev_end = min(ev.ends_at, today_end)
        if ev_start > current_time:
            duration = int((ev_start - current_time).total_seconds() // 60)
            if duration >= 15:
                free_windows.append(
                    TimeWindow(start=current_time, end=ev_start, duration_minutes=duration)
                )
        current_time = max(current_time, ev_end)

    if current_time < today_end:
        duration = int((today_end - current_time).total_seconds() // 60)
        if duration >= 15:
            free_windows.append(
                TimeWindow(start=current_time, end=today_end, duration_minutes=duration)
            )

    return free_windows


async def get_overdue_tasks(
    session: AsyncSession,
    workspace_id: UUID,
    limit: int = 10,
) -> List[TaskResponse]:
    """Retrieve overdue incomplete tasks ordered by due date ascending."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(Task)
        .where(
            Task.workspace_id == workspace_id,
            Task.is_deleted.is_(False),
            Task.status.notin_(["done", "cancelled", "archived"]),
            Task.due_at < now,
        )
        .order_by(Task.due_at.asc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return [TaskResponse.model_validate(t) for t in res.scalars().all()]


async def get_habits_today(
    session: AsyncSession,
    workspace_id: UUID,
    today_date: datetime.date,
) -> List[HabitSummary]:
    """Retrieve active habits and whether they were logged today."""
    stmt = select(Habit).where(
        Habit.workspace_id == workspace_id,
        Habit.is_archived.is_(False),
    ).order_by(Habit.created_at.asc())
    res = await session.execute(stmt)
    habits = res.scalars().all()
    if not habits:
        return []

    habit_ids = [h.id for h in habits]
    log_stmt = select(HabitLog.habit_id).where(
        HabitLog.workspace_id == workspace_id,
        HabitLog.habit_id.in_(habit_ids),
        HabitLog.logged_date == today_date,
    )
    logged_res = await session.execute(log_stmt)
    logged_habit_ids = set(logged_res.scalars().all())

    return [
        HabitSummary(
            id=str(h.id),
            title=h.title,
            target_count=h.target_count,
            current_streak=h.current_streak,
            best_streak=h.best_streak,
            completed_today=(h.id in logged_habit_ids),
        )
        for h in habits
    ]


async def get_budget_summary(
    session: AsyncSession,
    workspace_id: UUID,
    today_start: datetime,
    today_end: datetime,
) -> BudgetSummary:
    """Calculate aggregated balance, today expenses and active account count."""
    # 1. Accounts balance
    stmt = (
        select(func.sum(Account.balance_minor), func.count(Account.id))
        .where(
            Account.workspace_id == workspace_id,
            Account.is_archived.is_(False),
        )
    )
    res = await session.execute(stmt)
    row = res.one()
    total_balance = row[0] or 0
    active_count = row[1] or 0

    # 2. Today's expenses
    expense_stmt = (
        select(func.sum(Transaction.amount_minor))
        .where(
            Transaction.workspace_id == workspace_id,
            Transaction.status != "reversed",
            Transaction.type == "expense",
            Transaction.occurred_at >= today_start,
            Transaction.occurred_at <= today_end,
        )
    )
    expense_res = await session.execute(expense_stmt)
    today_spent = expense_res.scalar_one() or 0

    # 3. Monthly expenses (current month)
    month_start = today_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_stmt = (
        select(func.sum(Transaction.amount_minor))
        .where(
            Transaction.workspace_id == workspace_id,
            Transaction.status != "reversed",
            Transaction.type == "expense",
            Transaction.occurred_at >= month_start,
            Transaction.occurred_at <= today_end,
        )
    )
    monthly_res = await session.execute(monthly_stmt)
    monthly_spent = monthly_res.scalar_one() or 0

    return BudgetSummary(
        total_balance_minor=int(total_balance),
        today_spent_minor=int(today_spent),
        monthly_spent_minor=int(monthly_spent),
        monthly_limit_minor=1500000000,
        currency="UZS",
        active_accounts_count=active_count,
    )


async def get_today(
    session: AsyncSession,
    workspace_id: UUID,
    user_tz: str = "UTC",
) -> DashboardToday:
    """Consolidated today view: events, top tasks, overdue count, free slots, budget, habits, stats."""
    today_start, today_end = get_day_bounds(user_tz)
    events = await get_events_today(session, workspace_id, today_start, today_end)
    top_tasks = await get_top_tasks(session, workspace_id, limit=3)
    overdue_tasks = await get_overdue_tasks(session, workspace_id, limit=10)
    overdue_count = len(overdue_tasks)
    free_windows = calculate_free_windows(events, today_start, today_end)
    budget = await get_budget_summary(session, workspace_id, today_start, today_end)
    habits = await get_habits_today(session, workspace_id, today_start.date())

    # Calculate total active and completed today
    total_tasks_stmt = select(func.count(Task.id)).where(
        Task.workspace_id == workspace_id,
        Task.is_deleted.is_(False),
    )
    total_tasks = (await session.execute(total_tasks_stmt)).scalar_one() or 0

    completed_today_stmt = select(func.count(Task.id)).where(
        Task.workspace_id == workspace_id,
        Task.is_deleted.is_(False),
        Task.status == "done",
        Task.completed_at >= today_start,
    )
    completed_today = (await session.execute(completed_today_stmt)).scalar_one() or 0

    free_minutes = sum(w.duration_minutes for w in free_windows)
    free_hours = round(free_minutes / 60.0, 1)

    stats = DashboardStats(
        total_tasks=total_tasks,
        completed_tasks=completed_today,
        overdue_count=overdue_count,
        events_count=len(events),
        free_hours=free_hours,
    )

    return DashboardToday(
        events=events,
        top_tasks=top_tasks,
        overdue_tasks=overdue_tasks,
        overdue_count=overdue_count,
        free_windows=free_windows,
        budget_summary=budget,
        habits=habits,
        stats=stats,
    )


class DashboardService:
    """Consolidates cross-domain operational metrics for user dashboard views."""

    async def get_today(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_tz: str = "UTC",
    ) -> DashboardToday:
        return await get_today(session, workspace_id, user_tz)

    async def get_summary(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
    ) -> DashboardSummaryResponse:
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        today_end = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)

        # 1. Active tasks count
        stmt_tasks_count = (
            select(func.count(Task.id))
            .where(
                Task.workspace_id == workspace_id,
                Task.is_deleted.is_(False),
                Task.status.notin_(["done", "cancelled", "archived"]),
            )
        )
        res_tasks = await session.execute(stmt_tasks_count)
        active_tasks_count = res_tasks.scalar_one() or 0

        # 2. Tasks due today
        stmt_due_today = (
            select(func.count(Task.id))
            .where(
                Task.workspace_id == workspace_id,
                Task.is_deleted.is_(False),
                Task.status.notin_(["done", "cancelled", "archived"]),
                Task.due_at >= today_start,
                Task.due_at <= today_end,
            )
        )
        res_due = await session.execute(stmt_due_today)
        tasks_due_today_count = res_due.scalar_one() or 0

        # 3. Today's events count
        stmt_events = (
            select(func.count(Event.id))
            .where(
                Event.workspace_id == workspace_id,
                Event.status != "cancelled",
                Event.ends_at >= today_start,
                Event.starts_at <= today_end,
            )
        )
        res_events = await session.execute(stmt_events)
        today_events_count = res_events.scalar_one() or 0

        # 4. Total account balance
        stmt_balance = (
            select(func.sum(Account.balance_minor))
            .where(
                Account.workspace_id == workspace_id,
                Account.is_archived.is_(False),
            )
        )
        res_balance = await session.execute(stmt_balance)
        total_balance_minor = res_balance.scalar_one() or 0

        # 5. Unread notifications count
        stmt_notif = (
            select(func.count(Notification.id))
            .where(
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        res_notif = await session.execute(stmt_notif)
        unread_notifications_count = res_notif.scalar_one() or 0

        # 6. Recent active tasks (up to 5)
        stmt_recent_tasks = (
            select(Task)
            .where(
                Task.workspace_id == workspace_id,
                Task.is_deleted.is_(False),
                Task.status.notin_(["done", "cancelled", "archived"]),
            )
            .order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc())
            .limit(5)
        )
        recent_tasks_res = await session.execute(stmt_recent_tasks)
        recent_tasks = [TaskResponse.model_validate(t) for t in recent_tasks_res.scalars().all()]

        # 7. Upcoming events (up to 5)
        stmt_upcoming_events = (
            select(Event)
            .where(
                Event.workspace_id == workspace_id,
                Event.status != "cancelled",
                Event.ends_at >= now,
            )
            .order_by(Event.starts_at.asc())
            .limit(5)
        )
        upcoming_events_res = await session.execute(stmt_upcoming_events)
        upcoming_events = [EventResponse.model_validate(e) for e in upcoming_events_res.scalars().all()]

        return DashboardSummaryResponse(
            active_tasks_count=active_tasks_count,
            tasks_due_today_count=tasks_due_today_count,
            today_events_count=today_events_count,
            total_balance_minor=int(total_balance_minor),
            unread_notifications_count=unread_notifications_count,
            recent_tasks=recent_tasks,
            upcoming_events=upcoming_events,
        )


dashboard_service = DashboardService()
