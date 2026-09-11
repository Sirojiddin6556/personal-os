"""SQLAlchemy models for Calendar Events and Time Blocking."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Event(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Calendar schedule event with bi-directional synchronization metadata."""

    __tablename__ = "events"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="confirmed", nullable=False)
    sync_status: Mapped[str] = mapped_column(Text, default="local", nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_etag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


class TimeBlock(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Deep work time blocking linked to a specific Task or freeform focus slot."""

    __tablename__ = "time_blocks"

    task_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
