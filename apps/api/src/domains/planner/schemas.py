"""Pydantic schemas for Daily Planner, Habits, Journal, and Reminders."""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domains.calendar.schemas import TimeBlockResponse
from src.domains.tasks.schemas import TaskResponse


class HabitBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    frequency_type: str = Field(default="daily", pattern="^(daily|weekdays|weekends|weekly)$")
    target_count: int = Field(default=1, ge=1)


class HabitCreate(HabitBase):
    pass


class HabitUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency_type: Optional[str] = None
    target_count: Optional[int] = None
    is_archived: Optional[bool] = None


class HabitResponse(HabitBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    current_streak: int
    best_streak: int
    is_archived: bool
    is_completed_today: bool = False
    today_count: int = 0
    created_at: datetime
    updated_at: datetime


class DailyJournalInput(BaseModel):
    entry_date: date
    morning_intention: Optional[str] = None
    gratitude: Optional[str] = None
    notes: Optional[str] = None
    evening_reflection: Optional[str] = None
    mood: Optional[str] = None
    productivity_rating: Optional[int] = Field(default=None, ge=1, le=5)


class DailyJournalResponse(DailyJournalInput):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime


class PlannerReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    remind_at: datetime
    remind_type: str = Field(default="custom", pattern="^(task|habit|event|custom)$")
    related_id: Optional[UUID] = None


class PlannerReminderResponse(PlannerReminderCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    is_dismissed: bool
    created_at: datetime
    updated_at: datetime


class DailyAgendaStats(BaseModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    total_habits: int = 0
    completed_habits: int = 0
    total_timeblocks: int = 0


class DailyAgendaResponse(BaseModel):
    target_date: date
    tasks: List[TaskResponse]
    time_blocks: List[TimeBlockResponse]
    habits: List[HabitResponse]
    journal: Optional[DailyJournalResponse] = None
    reminders: List[PlannerReminderResponse]
    stats: DailyAgendaStats
