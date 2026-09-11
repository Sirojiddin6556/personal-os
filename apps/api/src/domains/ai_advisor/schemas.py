"""Pydantic v2 schemas for AI Advisor domain."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    """Raw user input string for intent and entity extraction."""

    text: str = Field(..., min_length=1, description="Raw input text to parse")


class ParseResult(BaseModel):
    """Result of Quick Add parser."""

    intent: str = Field(
        ...,
        description="Intent type: CREATE_TASK | CREATE_EVENT | CREATE_EXPENSE | CREATE_REMINDER | UNKNOWN",
    )
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted key-value entities such as title, amount, due_at, etc.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )


class ParseResponse(BaseModel):
    """API response model for input parsing."""

    intent: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class PlanRequest(BaseModel):
    """User prompt requesting schedule reorganization or planning."""

    request: str = Field(..., min_length=1, description="Schedule optimization request")


class AIPreviewPlan(BaseModel):
    """Schedule planner preview plan returning diff for user confirmation."""

    plan_id: UUID
    workspace_id: UUID
    status: str = Field(default="proposed", description="proposed | applied | rejected | expired")
    changes: List[Dict[str, Any]] = Field(default_factory=list, description="Proposed tool call actions")
    ai_explanation: str = Field(default="", description="Human-readable rationale for the plan")
    requires_confirmation: bool = True


class SearchRequest(BaseModel):
    """Semantic vector search query for knowledge notes."""

    query: str = Field(..., min_length=1, description="Semantic search query")
    limit: int = Field(default=10, ge=1, le=50, description="Max note chunks to retrieve")


class NoteChunkResponse(BaseModel):
    """Semantic note chunk retrieval response item."""

    id: UUID
    workspace_id: UUID
    note_id: UUID
    chunk_index: int
    content: str
    token_count: int
    score: Optional[float] = None
    similarity: Optional[float] = None

    model_config = {"from_attributes": True}


class MorningBriefResponse(BaseModel):
    """Structured morning briefing for executive focus."""

    date: str
    summary: str
    focus_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    upcoming_events: List[Dict[str, Any]] = Field(default_factory=list)
    financial_overview: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)


class RAGQARequest(BaseModel):
    """Knowledge question-answering request."""

    question: str = Field(..., min_length=1)
    limit_sources: int = Field(default=5, ge=1, le=20)


class RAGQAResponse(BaseModel):
    """Knowledge question-answering response with citations."""

    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0


class AIConsultRequest(BaseModel):
    """Freeform consultation request."""

    message: str
    focus_date: Optional[datetime] = None


class AIConsultResponse(BaseModel):
    """Freeform consultation response."""

    reply: str
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)


class AIActionConfirmResponse(BaseModel):
    """Result of confirming an AI proposal."""

    action_id: UUID
    status: str
    applied_at: datetime


class AIActionUndoResponse(BaseModel):
    """Result of undoing an applied AI action."""

    action_id: UUID
    status: str
    message: str
