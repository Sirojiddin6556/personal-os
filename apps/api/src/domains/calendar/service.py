"""Calendar and Time Blocking domain service."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.calendar.models import Event, TimeBlock
from src.domains.calendar.schemas import (
    EventCreate,
    EventUpdate,
    FreeBusyResponse,
    FreeWindow,
    TimeBlockCreate,
    TimeBlockUpdate,
)
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event


class CalendarService:
    """Operations for Events, TimeBlocks and schedule slot availability."""

    async def create_event(self, session: AsyncSession, workspace_id: UUID, body: EventCreate) -> Event:
        event = Event(
            id=uuid4(),
            workspace_id=workspace_id,
            title=body.title,
            description=body.description,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            is_all_day=body.is_all_day,
            location=body.location,
            status=body.status,
            sync_status="local",
            recurrence_rule=body.recurrence_rule,
            version=1,
        )
        session.add(event)
        await publish_event(
            session=session,
            event_type="calendar.event_created.v1",
            aggregate_type="event",
            aggregate_id=event.id,
            workspace_id=workspace_id,
            data={"title": event.title, "starts_at": event.starts_at.isoformat(), "ends_at": event.ends_at.isoformat()},
        )
        await session.commit()
        await session.refresh(event)
        return event

    async def list_events(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Event]:
        stmt = (
            select(Event)
            .where(
                Event.workspace_id == workspace_id,
                Event.ends_at >= start_date,
                Event.starts_at <= end_date,
                Event.status != "cancelled",
            )
            .order_by(Event.starts_at.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def create_time_block(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        body: TimeBlockCreate,
    ) -> TimeBlock:
        tb = TimeBlock(
            id=uuid4(),
            workspace_id=workspace_id,
            task_id=body.task_id,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            label=body.label,
            is_fixed=body.is_fixed,
        )
        session.add(tb)
        await publish_event(
            session=session,
            event_type="calendar.time_block_created.v1",
            aggregate_type="time_block",
            aggregate_id=tb.id,
            workspace_id=workspace_id,
            data={"starts_at": tb.starts_at.isoformat(), "ends_at": tb.ends_at.isoformat()},
        )
        await session.commit()
        await session.refresh(tb)
        return tb

    async def list_time_blocks(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> List[TimeBlock]:
        stmt = (
            select(TimeBlock)
            .where(
                TimeBlock.workspace_id == workspace_id,
                TimeBlock.ends_at >= start_date,
                TimeBlock.starts_at <= end_date,
            )
            .order_by(TimeBlock.starts_at.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_free_busy(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        start_dt: datetime,
        end_dt: datetime,
    ) -> FreeBusyResponse:
        """Compute free and busy intervals in the given range considering both events and fixed time blocks."""
        events = await self.list_events(session, workspace_id, start_dt, end_dt)
        time_blocks = await self.list_time_blocks(session, workspace_id, start_dt, end_dt)

        busy_intervals = []
        for ev in events:
            busy_intervals.append((max(ev.starts_at, start_dt), min(ev.ends_at, end_dt)))
        for tb in time_blocks:
            busy_intervals.append((max(tb.starts_at, start_dt), min(tb.ends_at, end_dt)))

        # Sort and merge overlapping intervals
        busy_intervals.sort(key=lambda x: x[0])
        merged_busy = []
        for s, e in busy_intervals:
            if not merged_busy:
                merged_busy.append((s, e))
            else:
                last_s, last_e = merged_busy[-1]
                if s <= last_e:
                    merged_busy[-1] = (last_s, max(last_e, e))
                else:
                    merged_busy.append((s, e))

        busy_windows = [
            FreeWindow(
                starts_at=s,
                ends_at=e,
                duration_minutes=int((e - s).total_seconds() // 60),
            )
            for s, e in merged_busy
        ]

        # Calculate inverse (free windows)
        free_windows = []
        cursor = start_dt
        for s, e in merged_busy:
            if s > cursor:
                diff_min = int((s - cursor).total_seconds() // 60)
                if diff_min >= 15:  # meaningful free slot
                    free_windows.append(FreeWindow(starts_at=cursor, ends_at=s, duration_minutes=diff_min))
            cursor = max(cursor, e)

        if cursor < end_dt:
            diff_min = int((end_dt - cursor).total_seconds() // 60)
            if diff_min >= 15:
                free_windows.append(FreeWindow(starts_at=cursor, ends_at=end_dt, duration_minutes=diff_min))

        return FreeBusyResponse(free_windows=free_windows, busy_windows=busy_windows)


calendar_service = CalendarService()
