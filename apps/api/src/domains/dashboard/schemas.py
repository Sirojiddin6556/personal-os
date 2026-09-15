"""Pydantic v2 schemas for the Dashboard overview."""

from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel

from src.domains.calendar.schemas import EventResponse
from src.domains.tasks.schemas import TaskResponse


class TimeWindow(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: int


class BudgetSummary(BaseModel):
    total_balance_minor: int
    today_spent_minor: int = 0
    monthly_spent_minor: int = 0
    monthly_limit_minor: int = 1500000000  # Default 15,000,000 UZS
    currency: str = "UZS"
    active_accounts_count: int


class HabitSummary(BaseModel):
    id: str
    title: str
    target_count: int
    current_streak: int
    best_streak: int
    completed_today: bool


class DashboardStats(BaseModel):
    total_tasks: int
    completed_tasks: int
    overdue_count: int
    events_count: int
    free_hours: float


class DashboardToday(BaseModel):
    events: List[EventResponse]
    top_tasks: List[TaskResponse]
    overdue_tasks: List[TaskResponse] = []
    overdue_count: int
    free_windows: List[TimeWindow]
    budget_summary: BudgetSummary
    habits: List[HabitSummary] = []
    stats: Optional[DashboardStats] = None


class DashboardSummaryResponse(BaseModel):
    active_tasks_count: int
    tasks_due_today_count: int
    today_events_count: int
    total_balance_minor: int
    unread_notifications_count: int
    recent_tasks: List[TaskResponse]
    upcoming_events: List[EventResponse]
