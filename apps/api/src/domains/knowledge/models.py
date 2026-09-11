"""SQLAlchemy models for Knowledge Notes and Vector Embeddings."""

from typing import List, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Note(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Knowledge base note formatted in Markdown."""

    __tablename__ = "notes"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Chunks relationship
    chunks: Mapped[List["NoteChunk"]] = relationship(
        "NoteChunk",
        back_populates="note",
        cascade="all, delete-orphan",
    )


class NoteChunk(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Segmented note chunk with 1536-dimensional embedding vector for semantic search."""

    __tablename__ = "note_chunks"

    note_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    note: Mapped["Note"] = relationship("Note", back_populates="chunks")
