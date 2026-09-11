"""Pydantic v2 schemas for Notifications domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    user_id: UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    channel: str = Field(default="in_app", pattern="^(in_app|telegram|email|push)$")
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


class NotificationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    title: str
    body: str
    channel: str
    priority: str
    status: str
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int
