"""Pydantic v2 schemas for the Dashboard overview."""

from typing import List
from pydantic import BaseModel

from src.domains.calendar.schemas import EventResponse
from src.domains.tasks.schemas import TaskResponse


class DashboardSummaryResponse(BaseModel):
    active_tasks_count: int
    tasks_due_today_count: int
    today_events_count: int
    total_balance_minor: int
    unread_notifications_count: int
    recent_tasks: List[TaskResponse]
    upcoming_events: List[EventResponse]
