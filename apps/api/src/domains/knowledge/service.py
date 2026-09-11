"""Knowledge domain service supporting markdown notes and full-text search."""

from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.knowledge.models import Note
from src.domains.knowledge.schemas import (
    NoteCreate,
    NoteResponse,
    NoteSearchResult,
    NoteUpdate,
)
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event


class KnowledgeService:
    """Operations for Notes, chunking and semantic/FTS search."""

    async def create_note(self, session: AsyncSession, workspace_id: UUID, body: NoteCreate) -> Note:
        note = Note(
            id=uuid4(),
            workspace_id=workspace_id,
            title=body.title,
            content_markdown=body.content_markdown,
            is_pinned=body.is_pinned,
            is_archived=False,
        )
        session.add(note)
        await publish_event(
            session=session,
            event_type="knowledge.note_created.v1",
            aggregate_type="note",
            aggregate_id=note.id,
            workspace_id=workspace_id,
            data={"title": note.title},
        )
        await session.commit()
        await session.refresh(note)
        return note

    async def get_note(self, session: AsyncSession, workspace_id: UUID, note_id: UUID) -> Note:
        stmt = select(Note).where(Note.id == note_id, Note.workspace_id == workspace_id)
        res = await session.execute(stmt)
        note = res.scalar_one_or_none()
        if not note:
            raise NotFoundError(resource="Note", identifier=note_id)
        return note

    async def update_note(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        note_id: UUID,
        body: NoteUpdate,
    ) -> Note:
        note = await self.get_note(session, workspace_id, note_id)
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(note, k, v)
        await publish_event(
            session=session,
            event_type="knowledge.note_updated.v1",
            aggregate_type="note",
            aggregate_id=note.id,
            workspace_id=workspace_id,
            data={"title": note.title},
        )
        await session.commit()
        await session.refresh(note)
        return note

    async def list_notes(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        is_pinned: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Note]:
        stmt = select(Note).where(Note.workspace_id == workspace_id, Note.is_archived.is_(False))
        if is_pinned is not None:
            stmt = stmt.where(Note.is_pinned == is_pinned)
        stmt = stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc()).limit(limit).offset(offset)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def search_notes(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        query: str,
        limit: int = 10,
    ) -> List[NoteSearchResult]:
        """Search notes using PostgreSQL full-text search with ranking."""
        # Using websearch_to_tsquery or plainto_tsquery with Russian dictionary
        fts_query = func.plainto_tsquery("russian", query)
        doc_vector = func.to_tsvector("russian", func.coalesce(Note.title, "") + " " + func.coalesce(Note.content_markdown, ""))
        rank = func.ts_rank(doc_vector, fts_query)

        stmt = (
            select(
                Note.id,
                Note.title,
                func.substr(Note.content_markdown, 1, 200).label("snippet"),
                rank.label("score"),
            )
            .where(
                Note.workspace_id == workspace_id,
                Note.is_archived.is_(False),
                or_(
                    doc_vector.op("@@")(fts_query),
                    Note.title.ilike(f"%{query}%"),
                    Note.content_markdown.ilike(f"%{query}%"),
                ),
            )
            .order_by(rank.desc(), Note.updated_at.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        results = []
        for r in res.all():
            results.append(
                NoteSearchResult(
                    note_id=r[0],
                    title=r[1],
                    snippet=r[2] or "",
                    score=float(r[3] or 1.0),
                )
            )
        return results


knowledge_service = KnowledgeService()
