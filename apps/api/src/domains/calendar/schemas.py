"""Pydantic v2 schemas for Calendar Events and Time Blocks."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool = False
    location: Optional[str] = None
    status: str = Field(default="confirmed", pattern="^(draft|confirmed|cancelled)$")
    recurrence_rule: Optional[str] = None

    @model_validator(mode="after")
    def validate_chronology(self):
        if self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at")
        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    location: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(draft|confirmed|cancelled)$")
    recurrence_rule: Optional[str] = None


class EventResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool
    location: Optional[str] = None
    status: str
    sync_status: str
    external_id: Optional[str] = None
    external_etag: Optional[str] = None
    recurrence_rule: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimeBlockCreate(BaseModel):
    task_id: Optional[UUID] = None
    starts_at: datetime
    ends_at: datetime
    label: Optional[str] = None
    is_fixed: bool = False

    @model_validator(mode="after")
    def validate_chronology(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be strictly greater than starts_at")
        return self


class TimeBlockUpdate(BaseModel):
    task_id: Optional[UUID] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    label: Optional[str] = None
    is_fixed: Optional[bool] = None


class TimeBlockResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    task_id: Optional[UUID] = None
    starts_at: datetime
    ends_at: datetime
    label: Optional[str] = None
    is_fixed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FreeWindow(BaseModel):
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int


class FreeBusyResponse(BaseModel):
    free_windows: List[FreeWindow]
    busy_windows: List[FreeWindow]
