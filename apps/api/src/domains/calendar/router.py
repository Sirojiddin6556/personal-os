"""Calendar API endpoints."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.calendar.schemas import (
    EventCreate,
    EventResponse,
    FreeBusyResponse,
    TimeBlockCreate,
    TimeBlockResponse,
)
from src.domains.calendar.service import calendar_service
from src.domains.identity.models import Workspace
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> EventResponse:
    event = await calendar_service.create_event(session, workspace.id, body)
    return EventResponse.model_validate(event)


@router.get("/events", response_model=List[EventResponse])
async def list_events(
    start_date: Optional[datetime] = Query(None, alias="from", description="Range start ISO datetime (from)"),
    end_date: Optional[datetime] = Query(None, alias="to", description="Range end ISO datetime (to)"),
    start: Optional[datetime] = Query(None, alias="start_date", description="Range start ISO datetime (start_date)"),
    end: Optional[datetime] = Query(None, alias="end_date", description="Range end ISO datetime (end_date)"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[EventResponse]:
    from datetime import timedelta
    from_dt = start_date or start or (datetime.now(timezone.utc) - timedelta(days=30))
    to_dt = end_date or end or (datetime.now(timezone.utc) + timedelta(days=60))
    events = await calendar_service.list_events(session, workspace.id, from_dt, to_dt)
    return [EventResponse.model_validate(ev) for ev in events]


@router.post("/time-blocks", response_model=TimeBlockResponse, status_code=status.HTTP_201_CREATED)
async def create_time_block(
    body: TimeBlockCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TimeBlockResponse:
    tb = await calendar_service.create_time_block(session, workspace.id, body)
    return TimeBlockResponse.model_validate(tb)


@router.get("/time-blocks", response_model=List[TimeBlockResponse])
async def list_time_blocks(
    start_date: Optional[datetime] = Query(None, alias="from", description="Range start ISO datetime"),
    end_date: Optional[datetime] = Query(None, alias="to", description="Range end ISO datetime"),
    start: Optional[datetime] = Query(None, alias="start_date"),
    end: Optional[datetime] = Query(None, alias="end_date"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[TimeBlockResponse]:
    from datetime import timedelta
    from_dt = start_date or start or (datetime.now(timezone.utc) - timedelta(days=30))
    to_dt = end_date or end or (datetime.now(timezone.utc) + timedelta(days=60))
    blocks = await calendar_service.list_time_blocks(session, workspace.id, from_dt, to_dt)
    return [TimeBlockResponse.model_validate(b) for b in blocks]


@router.get("/free-busy", response_model=FreeBusyResponse)
async def get_free_busy(
    start_date: Optional[datetime] = Query(None, alias="from", description="Range start ISO datetime"),
    end_date: Optional[datetime] = Query(None, alias="to", description="Range end ISO datetime"),
    start: Optional[datetime] = Query(None, alias="start_date"),
    end: Optional[datetime] = Query(None, alias="end_date"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> FreeBusyResponse:
    from datetime import timedelta
    from_dt = start_date or start or (datetime.now(timezone.utc) - timedelta(days=7))
    to_dt = end_date or end or (datetime.now(timezone.utc) + timedelta(days=14))
    return await calendar_service.get_free_busy(session, workspace.id, from_dt, to_dt)
