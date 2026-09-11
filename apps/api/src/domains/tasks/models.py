"""SQLAlchemy Task model with multi-tenant isolation, hierarchy, and optimistic locking."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Task(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Task item supporting hierarchy, estimates, tracking, and optimistic versioning."""

    __tablename__ = "tasks"

    project_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="inbox", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(Text, default="medium", nullable=False)
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    estimate_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tracked_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    waiting_for_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Hierarchy relationship
    subtasks: Mapped[List["Task"]] = relationship(
        "Task",
        backref="parent",
        remote_side="Task.id",
        cascade="all, delete-orphan",
    )
