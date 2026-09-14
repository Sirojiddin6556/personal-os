"""SQLAlchemy Task model with multi-tenant isolation, hierarchy, soft delete, and optimistic locking."""

from datetime import datetime
import enum
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class TaskStatus(str, enum.Enum):
    INBOX = "inbox"
    TODO = "todo"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


TaskPriority = Priority  # Backwards compatibility alias


class Task(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Task item supporting hierarchy, estimates, tracking, and optimistic versioning."""

    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="inbox")
    priority: Mapped[str] = mapped_column(Text, nullable=False, default="medium")
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    estimate_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Core metadata columns
    tracked_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    waiting_for_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    @validates("priority")
    def validate_priority(self, key: str, value: Optional[str]) -> str:
        if not value:
            return "medium"
        val = str(value).lower().strip()
        mapping = {
            "p1": "critical",
            "critical": "critical",
            "urgent": "critical",
            "p2": "high",
            "high": "high",
            "p3": "medium",
            "medium": "medium",
            "normal": "medium",
            "p4": "low",
            "low": "low",
        }
        return mapping.get(val, "medium")

    @validates("status")
    def validate_status(self, key: str, value: Optional[str]) -> str:
        if not value:
            return "inbox"
        val = str(value).lower().strip()
        allowed = {"inbox", "todo", "scheduled", "in_progress", "waiting", "done", "cancelled", "archived"}
        return val if val in allowed else "inbox"

    # Hierarchy relationship
    parent: Mapped[Optional["Task"]] = relationship(
        "Task",
        remote_side="Task.id",
        back_populates="subtasks",
    )
    subtasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('inbox','todo','scheduled','in_progress','waiting','done','cancelled','archived')",
            name="chk_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low','medium','high','critical')",
            name="chk_tasks_priority",
        ),
        CheckConstraint(
            "status != 'done' OR completed_at IS NOT NULL",
            name="chk_tasks_done_completed_at",
        ),
        Index("ix_tasks_workspace_status", "workspace_id", "status"),
        Index(
            "ix_tasks_workspace_due",
            "workspace_id",
            "due_at",
            postgresql_where=text("status NOT IN ('done','archived','cancelled')"),
        ),
    )
