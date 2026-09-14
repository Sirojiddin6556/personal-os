"""Pydantic v2 schemas for the Dashboard overview."""

from datetime import datetime
from typing import List
from pydantic import BaseModel

from src.domains.calendar.schemas import EventResponse
from src.domains.tasks.schemas import TaskResponse


class TimeWindow(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: int


class BudgetSummary(BaseModel):
    total_balance_minor: int
    currency: str = "UZS"
    active_accounts_count: int


class DashboardToday(BaseModel):
    events: List[EventResponse]
    top_tasks: List[TaskResponse]
    overdue_count: int
    free_windows: List[TimeWindow]
    budget_summary: BudgetSummary


class DashboardSummaryResponse(BaseModel):
    active_tasks_count: int
    tasks_due_today_count: int
    today_events_count: int
    total_balance_minor: int
    unread_notifications_count: int
    recent_tasks: List[TaskResponse]
    upcoming_events: List[EventResponse]
