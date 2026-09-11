"""FastAPI router for Daily Planner, Habits, Journal, and Reminders."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.domains.planner.schemas import (
    DailyAgendaResponse,
    DailyJournalInput,
    DailyJournalResponse,
    HabitCreate,
    HabitResponse,
    PlannerReminderCreate,
    PlannerReminderResponse,
)
from src.domains.planner.service import planner_service
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/planner", tags=["planner"])


@router.get("/agenda", response_model=DailyAgendaResponse, summary="Get full daily planner agenda")
async def get_daily_agenda(
    target_date: Optional[date] = Query(None, description="Target date for agenda (defaults to today)"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> DailyAgendaResponse:
    return await planner_service.get_daily_agenda(session, workspace.id, target_date)


@router.get("/habits", response_model=List[HabitResponse], summary="List habits with today completion status")
async def list_habits(
    target_date: Optional[date] = Query(None, description="Target date for habit tracking"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[HabitResponse]:
    return await planner_service.list_habits(session, workspace.id, target_date)


@router.post("/habits", response_model=HabitResponse, status_code=status.HTTP_201_CREATED, summary="Create a new habit")
async def create_habit(
    body: HabitCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> HabitResponse:
    habit = await planner_service.create_habit(session, workspace.id, body)
    return HabitResponse(
        id=habit.id,
        workspace_id=habit.workspace_id,
        title=habit.title,
        description=habit.description,
        frequency_type=habit.frequency_type,
        target_count=habit.target_count,
        current_streak=0,
        best_streak=0,
        is_archived=False,
        is_completed_today=False,
        today_count=0,
        created_at=habit.created_at,
        updated_at=habit.updated_at,
    )


@router.post("/habits/{habit_id}/toggle", response_model=HabitResponse, summary="Toggle habit completion for date")
async def toggle_habit(
    habit_id: UUID,
    target_date: Optional[date] = Query(None, description="Target date to toggle"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> HabitResponse:
    return await planner_service.toggle_habit_completion(session, workspace.id, habit_id, target_date)


@router.delete("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a habit")
async def delete_habit(
    habit_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await planner_service.delete_habit(session, workspace.id, habit_id)


@router.get("/journal", response_model=Optional[DailyJournalResponse], summary="Get daily journal entry for date")
async def get_journal(
    entry_date: date = Query(..., description="Date for journal entry"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Optional[DailyJournalResponse]:
    entry = await planner_service.get_journal_entry(session, workspace.id, entry_date)
    return DailyJournalResponse.model_validate(entry) if entry else None


@router.put("/journal", response_model=DailyJournalResponse, summary="Save or update daily journal entry")
async def save_journal(
    body: DailyJournalInput,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> DailyJournalResponse:
    entry = await planner_service.save_journal_entry(session, workspace.id, body)
    return DailyJournalResponse.model_validate(entry)


@router.get("/reminders", response_model=List[PlannerReminderResponse], summary="List active scheduled reminders")
async def list_reminders(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[PlannerReminderResponse]:
    reminders = await planner_service.list_active_reminders(session, workspace.id)
    return [PlannerReminderResponse.model_validate(r) for r in reminders]


@router.post("/reminders", response_model=PlannerReminderResponse, status_code=status.HTTP_201_CREATED, summary="Create a new reminder")
async def create_reminder(
    body: PlannerReminderCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> PlannerReminderResponse:
    reminder = await planner_service.create_reminder(session, workspace.id, body)
    return PlannerReminderResponse.model_validate(reminder)


@router.post("/reminders/{reminder_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT, summary="Dismiss an active reminder")
async def dismiss_reminder(
    reminder_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await planner_service.dismiss_reminder(session, workspace.id, reminder_id)
