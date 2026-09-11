import uuid
from datetime import datetime
from sqlalchemy import TIMESTAMP, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    pass


class UUIDMixin:
    """Primary key mixin using PostgreSQL UUIDv4 / UUIDv7 with gen_random_uuid() default."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Standard timestamp mixin with timezone-aware clock timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("clock_timestamp()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("clock_timestamp()"),
        onupdate=text("clock_timestamp()"),
        nullable=False,
    )


class WorkspaceMixin:
    """Multi-tenancy mixin ensuring strict isolation with workspace_id foreign key and indexing."""
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
