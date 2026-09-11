"""Pydantic v2 schemas for Projects, Goals and Milestones."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = "general"
    target_date: Optional[date] = None
    status: str = Field(default="active", pattern="^(active|completed|paused|archived)$")
    progress_percentage: int = Field(default=0, ge=0, le=100)


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[str] = Field(default=None, pattern="^(active|completed|paused|archived)$")
    progress_percentage: Optional[int] = Field(default=None, ge=0, le=100)


class GoalResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    description: Optional[str] = None
    category: str
    target_date: Optional[date] = None
    status: str
    progress_percentage: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    goal_id: Optional[UUID] = None
    color: str = Field(default="#3B82F6", pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|completed|on_hold|archived)$")
    target_date: Optional[date] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    goal_id: Optional[UUID] = None
    color: Optional[str] = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|completed|on_hold|archived)$")
    target_date: Optional[date] = None


class ProjectResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    goal_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    color: str
    icon: Optional[str] = None
    status: str
    target_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    due_date: date
    goal_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    status: str = Field(default="pending", pattern="^(pending|achieved|missed)$")


class MilestoneUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    due_date: Optional[date] = None
    status: Optional[str] = Field(default=None, pattern="^(pending|achieved|missed)$")


class MilestoneResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    goal_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    title: str
    due_date: date
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
