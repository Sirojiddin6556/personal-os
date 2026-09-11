"""SQLAlchemy models for AI Actions, Tool Calls Telemetry, and Plan Undo Logs."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class AIAction(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Proposal or applied state modification planned by the AI Assistant."""

    __tablename__ = "ai_actions"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    diff_payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    risk_tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="proposed", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class AIToolCall(Base, UUIDMixin, WorkspaceMixin):
    """Fine-grained audit and telemetry record for LLM tool invocation."""

    __tablename__ = "ai_tool_calls"

    action_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_actions.id", ondelete="CASCADE"),
        nullable=True,
    )
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_arguments: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    output_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="success", nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class AIPlanUndoLog(Base, UUIDMixin, WorkspaceMixin):
    """Snapshot store allowing rollback of AI-applied bulk modifications."""

    __tablename__ = "ai_plan_undo_logs"

    action_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_actions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    entity_snapshots: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
