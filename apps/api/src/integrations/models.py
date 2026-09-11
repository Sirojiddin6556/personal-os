"""SQLAlchemy models for Integrations, Sync States, External Mappings and Inbox Quick Capture."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Integration(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """External service connection credentials and state."""

    __tablename__ = "integrations"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="connected", nullable=False)
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ExternalMapping(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Bi-directional mapping between local entity UUIDs and foreign provider IDs."""

    __tablename__ = "external_mappings"

    integration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    internal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    sync_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class SyncState(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Opaque delta sync tokens for incremental pagination/polling."""

    __tablename__ = "sync_states"

    integration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    sync_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="synced", nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class InboxItem(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Raw quick-capture inbox item from Telegram, web extensions or mobile."""

    __tablename__ = "inbox_items"

    source: Mapped[str] = mapped_column(Text, default="web", nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    processed_entity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_entity_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
