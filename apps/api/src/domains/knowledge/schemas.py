"""Pydantic v2 schemas for the Knowledge domain."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content_markdown: str = ""
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    content_markdown: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None


class NoteResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    content_markdown: str
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteSearchResult(BaseModel):
    note_id: UUID
    title: str
    snippet: str
    score: float


class SearchQuery(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
