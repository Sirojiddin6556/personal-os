"""SQLAlchemy models for Daily Planner, Habits, Journal, and Reminders."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Habit(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Habit or daily routine entity."""

    __tablename__ = "habits"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frequency_type: Mapped[str] = mapped_column(Text, default="daily", nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    logs: Mapped[list["HabitLog"]] = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")


class HabitLog(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Daily completion log for a habit."""

    __tablename__ = "habit_logs"
    __table_args__ = (
        UniqueConstraint("habit_id", "logged_date", name="uq_habit_logs_habit_date"),
    )

    habit_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("habits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    logged_date: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    habit: Mapped["Habit"] = relationship("Habit", back_populates="logs")


class DailyJournal(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Daily journal and reflection entry."""

    __tablename__ = "daily_journals"
    __table_args__ = (
        UniqueConstraint("workspace_id", "entry_date", name="uq_daily_journals_workspace_date"),
    )

    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    morning_intention: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gratitude: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evening_reflection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mood: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    productivity_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class PlannerReminder(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Scheduled planner reminder."""

    __tablename__ = "planner_reminders"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    remind_type: Mapped[str] = mapped_column(Text, default="custom", nullable=False)
    related_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
