"""Pydantic v2 schemas for the Tasks domain."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.domains.tasks.enums import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.INBOX
    priority: TaskPriority = TaskPriority.MEDIUM
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    due_at: Optional[datetime] = None
    estimate_minutes: Optional[int] = Field(default=None, gt=0)
    waiting_for_reason: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    due_at: Optional[datetime] = None
    estimate_minutes: Optional[int] = Field(default=None, gt=0)
    tracked_seconds: Optional[int] = Field(default=None, ge=0)
    rank: Optional[int] = None
    waiting_for_reason: Optional[str] = None


class TaskResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    estimate_minutes: Optional[int] = None
    tracked_seconds: int
    rank: int
    version: int
    waiting_for_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KanbanColumnResponse(BaseModel):
    status: str
    count: int
    tasks: List[TaskResponse]


class KanbanBoardResponse(BaseModel):
    columns: Dict[str, KanbanColumnResponse]
