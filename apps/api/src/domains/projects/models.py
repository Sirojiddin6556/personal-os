"""SQLAlchemy models for Projects, Strategic Goals and Milestones."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Goal(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """High-level strategic goal tracking progress across projects."""

    __tablename__ = "goals"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, default="general", nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="goal")
    milestones: Mapped[List["Milestone"]] = relationship("Milestone", back_populates="goal")


class Project(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Container grouping tasks and initiatives under a shared outcome."""

    __tablename__ = "projects"

    goal_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("goals.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#3B82F6", nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    github_repo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_default_branch: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="main")

    # Relationships
    goal: Mapped[Optional["Goal"]] = relationship("Goal", back_populates="projects")
    milestones: Mapped[List["Milestone"]] = relationship("Milestone", back_populates="project")


class Milestone(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Key milestone deadline associated with a Goal or Project."""

    __tablename__ = "milestones"

    goal_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("goals.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)

    # Relationships
    goal: Mapped[Optional["Goal"]] = relationship("Goal", back_populates="milestones")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="milestones")
