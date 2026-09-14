"""Pydantic v2 schemas for the Tasks domain."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


_PRIORITY_ALIASES = {
    "p1": "critical",
    "p2": "high",
    "p3": "medium",
    "p4": "low",
}


def normalize_priority(value: str) -> str:
    """Accept UI priority tiers while keeping the database contract canonical."""
    normalized = value.strip().lower()
    return _PRIORITY_ALIASES.get(normalized, normalized)


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = "medium"
    status: Optional[str] = "inbox"
    due_at: Optional[datetime] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    estimate_minutes: Optional[int] = Field(None, ge=1, le=1440)
    waiting_for_reason: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def normalize_priority_alias(cls, value: str) -> str:
        return normalize_priority(value)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None
    estimate_minutes: Optional[int] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    tracked_seconds: Optional[int] = None
    rank: Optional[int] = None
    waiting_for_reason: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def normalize_priority_alias(cls, value: Optional[str]) -> Optional[str]:
        return normalize_priority(value) if value is not None else None


class TaskResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    estimate_minutes: Optional[int] = None
    tracked_seconds: Optional[int] = 0
    rank: Optional[int] = 0
    version: int
    is_deleted: bool = False
    waiting_for_reason: Optional[str] = None
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
