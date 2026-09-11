"""Calendar API endpoints."""

from datetime import datetime, timezone
from typing import List
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
    start_date: datetime = Query(..., description="Range start ISO datetime"),
    end_date: datetime = Query(..., description="Range end ISO datetime"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[EventResponse]:
    events = await calendar_service.list_events(session, workspace.id, start_date, end_date)
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
    start_date: datetime = Query(..., description="Range start ISO datetime"),
    end_date: datetime = Query(..., description="Range end ISO datetime"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[TimeBlockResponse]:
    blocks = await calendar_service.list_time_blocks(session, workspace.id, start_date, end_date)
    return [TimeBlockResponse.model_validate(b) for b in blocks]


@router.get("/free-busy", response_model=FreeBusyResponse)
async def get_free_busy(
    start_date: datetime = Query(..., description="Range start ISO datetime"),
    end_date: datetime = Query(..., description="Range end ISO datetime"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> FreeBusyResponse:
    return await calendar_service.get_free_busy(session, workspace.id, start_date, end_date)
