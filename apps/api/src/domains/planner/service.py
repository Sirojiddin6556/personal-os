"""Domain service for Daily Planner, Habits, Journal, and Reminders."""

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.calendar.models import TimeBlock
from src.domains.calendar.schemas import TimeBlockResponse
from src.domains.planner.models import DailyJournal, Habit, HabitLog, PlannerReminder
from src.domains.planner.schemas import (
    DailyAgendaResponse,
    DailyAgendaStats,
    DailyJournalInput,
    HabitCreate,
    HabitResponse,
    HabitUpdate,
    PlannerReminderCreate,
)
from src.domains.tasks.models import Task
from src.domains.tasks.schemas import TaskResponse
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event


class PlannerService:
    """Service handling daily planning, habit routines, journaling, and proactive reminders."""

    # -------------------------------------------------------------------------
    # HABITS
    # -------------------------------------------------------------------------

    async def list_habits(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        target_date: Optional[date] = None,
    ) -> List[HabitResponse]:
        check_date = target_date or datetime.now(timezone.utc).date()

        stmt = (
            select(Habit)
            .where(
                Habit.workspace_id == workspace_id,
                Habit.is_archived == False,
            )
            .order_by(Habit.created_at.asc())
        )
        res = await session.execute(stmt)
        habits = res.scalars().all()

        # Fetch today's logs for these habits
        habit_ids = [h.id for h in habits]
        logs_map = {}
        if habit_ids:
            log_stmt = select(HabitLog).where(
                HabitLog.workspace_id == workspace_id,
                HabitLog.habit_id.in_(habit_ids),
                HabitLog.logged_date == check_date,
            )
            log_res = await session.execute(log_stmt)
            for log in log_res.scalars().all():
                logs_map[log.habit_id] = log

        result = []
        for h in habits:
            log = logs_map.get(h.id)
            today_count = log.count if log else 0
            is_completed = today_count >= h.target_count
            resp = HabitResponse(
                id=h.id,
                workspace_id=h.workspace_id,
                title=h.title,
                description=h.description,
                frequency_type=h.frequency_type,
                target_count=h.target_count,
                current_streak=h.current_streak,
                best_streak=h.best_streak,
                is_archived=h.is_archived,
                is_completed_today=is_completed,
                today_count=today_count,
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
            result.append(resp)
        return result

    async def create_habit(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        data: HabitCreate,
    ) -> Habit:
        habit = Habit(
            workspace_id=workspace_id,
            title=data.title,
            description=data.description,
            frequency_type=data.frequency_type,
            target_count=data.target_count,
            current_streak=0,
            best_streak=0,
        )
        session.add(habit)
        await session.flush()
        return habit

    async def toggle_habit_completion(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        habit_id: UUID,
        target_date: Optional[date] = None,
    ) -> HabitResponse:
        check_date = target_date or datetime.now(timezone.utc).date()

        stmt = select(Habit).where(Habit.id == habit_id, Habit.workspace_id == workspace_id)
        res = await session.execute(stmt)
        habit = res.scalar_one_or_none()
        if not habit:
            raise NotFoundError("Habit not found")

        log_stmt = select(HabitLog).where(
            HabitLog.workspace_id == workspace_id,
            HabitLog.habit_id == habit_id,
            HabitLog.logged_date == check_date,
        )
        log_res = await session.execute(log_stmt)
        log = log_res.scalar_one_or_none()

        if log:
            # If already logged, toggle off
            await session.delete(log)
            if habit.current_streak > 0:
                habit.current_streak = max(0, habit.current_streak - 1)
            is_completed = False
            today_count = 0
        else:
            # Create log and increment streak
            new_log = HabitLog(
                workspace_id=workspace_id,
                habit_id=habit_id,
                logged_date=check_date,
                count=habit.target_count,
            )
            session.add(new_log)
            habit.current_streak += 1
            if habit.current_streak > habit.best_streak:
                habit.best_streak = habit.current_streak
            is_completed = True
            today_count = habit.target_count

        await session.flush()

        return HabitResponse(
            id=habit.id,
            workspace_id=habit.workspace_id,
            title=habit.title,
            description=habit.description,
            frequency_type=habit.frequency_type,
            target_count=habit.target_count,
            current_streak=habit.current_streak,
            best_streak=habit.best_streak,
            is_archived=habit.is_archived,
            is_completed_today=is_completed,
            today_count=today_count,
            created_at=habit.created_at,
            updated_at=habit.updated_at,
        )

    async def delete_habit(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        habit_id: UUID,
    ) -> None:
        stmt = delete(Habit).where(Habit.id == habit_id, Habit.workspace_id == workspace_id)
        await session.execute(stmt)

    # -------------------------------------------------------------------------
    # DAILY JOURNAL
    # -------------------------------------------------------------------------

    async def get_journal_entry(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        entry_date: date,
    ) -> Optional[DailyJournal]:
        stmt = select(DailyJournal).where(
            DailyJournal.workspace_id == workspace_id,
            DailyJournal.entry_date == entry_date,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_journal_entry(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        data: DailyJournalInput,
    ) -> DailyJournal:
        stmt = select(DailyJournal).where(
            DailyJournal.workspace_id == workspace_id,
            DailyJournal.entry_date == data.entry_date,
        )
        res = await session.execute(stmt)
        entry = res.scalar_one_or_none()

        if entry:
            entry.morning_intention = data.morning_intention
            entry.gratitude = data.gratitude
            entry.notes = data.notes
            entry.evening_reflection = data.evening_reflection
            entry.mood = data.mood
            entry.productivity_rating = data.productivity_rating
        else:
            entry = DailyJournal(
                workspace_id=workspace_id,
                entry_date=data.entry_date,
                morning_intention=data.morning_intention,
                gratitude=data.gratitude,
                notes=data.notes,
                evening_reflection=data.evening_reflection,
                mood=data.mood,
                productivity_rating=data.productivity_rating,
            )
            session.add(entry)

        await session.flush()
        return entry

    # -------------------------------------------------------------------------
    # REMINDERS
    # -------------------------------------------------------------------------

    async def create_reminder(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        data: PlannerReminderCreate,
    ) -> PlannerReminder:
        reminder = PlannerReminder(
            workspace_id=workspace_id,
            title=data.title,
            remind_at=data.remind_at,
            remind_type=data.remind_type,
            related_id=data.related_id,
            is_dismissed=False,
        )
        session.add(reminder)
        await session.flush()

        # Emit WebSocket event for real-time notification
        await publish_event(
            session=session,
            workspace_id=workspace_id,
            event_type="reminder.created",
            aggregate_type="reminder",
            aggregate_id=reminder.id,
            payload={
                "id": str(reminder.id),
                "title": reminder.title,
                "remind_at": reminder.remind_at.isoformat(),
                "remind_type": reminder.remind_type,
            },
        )
        return reminder

    async def list_active_reminders(
        self,
        session: AsyncSession,
        workspace_id: UUID,
    ) -> List[PlannerReminder]:
        stmt = (
            select(PlannerReminder)
            .where(
                PlannerReminder.workspace_id == workspace_id,
                PlannerReminder.is_dismissed == False,
            )
            .order_by(PlannerReminder.remind_at.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def dismiss_reminder(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        reminder_id: UUID,
    ) -> None:
        stmt = select(PlannerReminder).where(
            PlannerReminder.id == reminder_id,
            PlannerReminder.workspace_id == workspace_id,
        )
        res = await session.execute(stmt)
        reminder = res.scalar_one_or_none()
        if reminder:
            reminder.is_dismissed = True
            await session.flush()

    # -------------------------------------------------------------------------
    # DAILY AGENDA AGGREGATOR
    # -------------------------------------------------------------------------

    async def get_daily_agenda(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        target_date: Optional[date] = None,
    ) -> DailyAgendaResponse:
        current_day = target_date or datetime.now(timezone.utc).date()
        start_of_day = datetime.combine(current_day, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(current_day, time.max, tzinfo=timezone.utc)

        # 1. Fetch Day's Tasks
        task_stmt = (
            select(Task)
            .where(
                Task.workspace_id == workspace_id,
                (
                    (Task.due_at >= start_of_day) & (Task.due_at <= end_of_day)
                    | (Task.status.in_(["inbox", "todo", "in_progress", "scheduled"]))
                ),
            )
            .order_by(Task.rank.asc(), Task.due_at.asc().nulls_last())
            .limit(50)
        )
        task_res = await session.execute(task_stmt)
        tasks = task_res.scalars().all()
        task_responses = [TaskResponse.model_validate(t) for t in tasks]

        # 2. Fetch Time Blocks
        tb_stmt = (
            select(TimeBlock)
            .where(
                TimeBlock.workspace_id == workspace_id,
                TimeBlock.starts_at >= start_of_day,
                TimeBlock.starts_at <= end_of_day,
            )
            .order_by(TimeBlock.starts_at.asc())
        )
        tb_res = await session.execute(tb_stmt)
        time_blocks = tb_res.scalars().all()
        tb_responses = [TimeBlockResponse.model_validate(tb) for tb in time_blocks]

        # 3. Fetch Habits with today completion
        habits = await self.list_habits(session, workspace_id, current_day)

        # 4. Fetch Journal
        journal = await self.get_journal_entry(session, workspace_id, current_day)

        # 5. Fetch Reminders
        reminders = await self.list_active_reminders(session, workspace_id)

        # 6. Compute Stats
        completed_tasks = sum(1 for t in tasks if t.status == "done")
        completed_habits = sum(1 for h in habits if h.is_completed_today)

        stats = DailyAgendaStats(
            total_tasks=len(tasks),
            completed_tasks=completed_tasks,
            total_habits=len(habits),
            completed_habits=completed_habits,
            total_timeblocks=len(time_blocks),
        )

        return DailyAgendaResponse(
            target_date=current_day,
            tasks=task_responses,
            time_blocks=tb_responses,
            habits=habits,
            journal=journal,
            reminders=reminders,
            stats=stats,
        )


planner_service = PlannerService()
