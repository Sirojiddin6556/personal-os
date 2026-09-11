"""Knowledge domain service supporting markdown notes, pgvector HNSW RAG, and full-text search."""

import hashlib
import logging
import math
import random
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.domains.knowledge.models import Note, NoteChunk
from src.domains.knowledge.schemas import (
    NoteCreate,
    NoteResponse,
    NoteSearchResult,
    NoteUpdate,
)
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event

logger = logging.getLogger("personal_os.knowledge.service")


@dataclass
class TextChunk:
    index: int
    text: str


def chunk_text(content: str, chunk_size: int = 512, overlap: int = 64) -> List[TextChunk]:
    """Segment note text into overlapping chunks for vector embedding and retrieval."""
    if not content or not content.strip():
        return []

    cleaned = content.strip()
    if len(cleaned) <= chunk_size:
        return [TextChunk(index=0, text=cleaned)]

    chunks: List[TextChunk] = []
    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size

    idx = 0
    start = 0
    total_len = len(cleaned)

    while start < total_len:
        end = min(start + chunk_size, total_len)
        if end < total_len:
            # Find whitespace to avoid splitting mid-word
            last_space = cleaned.rfind(" ", start, end)
            if last_space > start + (chunk_size // 2):
                end = last_space

        chunk_slice = cleaned[start:end].strip()
        if chunk_slice:
            chunks.append(TextChunk(index=idx, text=chunk_slice))
            idx += 1

        if end >= total_len:
            break

        start = end - overlap if end - overlap > start else end

    return chunks


def _generate_deterministic_embedding(text: str, dim: int = 1536) -> List[float]:
    """Generate a normalized 1536-dimensional pseudo-random vector for deterministic offline testing."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(h[:8], "big")
    rng = random.Random(seed)

    raw = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [round(x / norm, 6) for x in raw]


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Obtain 1536-dimensional embeddings using OpenAI text-embedding-3-small or offline fallback."""
    if not texts:
        return []

    # Try OpenAI if configured
    if settings.openai_api_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "text-embedding-3-small",
                        "input": texts,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    return [item["embedding"] for item in data["data"]]
                else:
                    logger.warning("OpenAI embedding returned %d: %s", res.status_code, res.text)
        except Exception as ex:
            logger.warning("OpenAI embedding failed, falling back to local vectors: %s", ex)

    # Deterministic fallback vectors
    return [_generate_deterministic_embedding(t) for t in texts]


async def index_note(session: AsyncSession, workspace_id: UUID, note_id: UUID, content: str) -> None:
    """Chunk note content + embed + store in note_chunks with tenant isolation."""
    # 1. Chunking (512 tokens/chars, overlap 64)
    chunks = chunk_text(content, chunk_size=512, overlap=64)
    if not chunks:
        # Delete any existing chunks if content is empty
        await session.execute(delete(NoteChunk).where(NoteChunk.note_id == note_id))
        await session.commit()
        return

    # 2. Embed via OpenAI text-embedding-3-small
    embeddings = await embed_texts([c.text for c in chunks])

    # 3. DELETE old chunks + INSERT new (transactional)
    await session.execute(delete(NoteChunk).where(NoteChunk.note_id == note_id))
    for chunk, embedding in zip(chunks, embeddings):
        session.add(
            NoteChunk(
                note_id=note_id,
                workspace_id=workspace_id,  # MANDATORY for multi-tenant isolation
                content=chunk.text,
                chunk_index=chunk.index,
                embedding=embedding,
                token_count=max(1, len(chunk.text.split())),
            )
        )
    await session.commit()


async def search_notes(
    session: AsyncSession,
    workspace_id: UUID,
    query: str,
    limit: int = 10,
) -> List[NoteChunk]:
    """Semantic search: workspace-scoped vector similarity using pgvector cosine distance."""
    query_embedding = await embed_texts([query])

    # WHERE workspace_id = $1 BEFORE vector search (Zero Cross-Tenant)
    result = await session.execute(
        select(NoteChunk)
        .where(NoteChunk.workspace_id == workspace_id)  # PRE-FILTER
        .order_by(NoteChunk.embedding.cosine_distance(query_embedding[0]))
        .limit(limit)
    )
    return list(result.scalars().all())


class KnowledgeService:
    """Operations for Notes, semantic RAG chunking and hybrid full-text search."""

    async def index_note(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        note_id: UUID,
        content: str,
    ) -> None:
        """Chunk note content + embed + store in note_chunks with tenant isolation."""
        return await index_note(session, workspace_id, note_id, content)

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

        # Index note content into note_chunks asynchronously
        if note.content_markdown:
            await index_note(session, workspace_id, note.id, note.content_markdown)

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

        # Re-index if content updated
        if "content_markdown" in data:
            await index_note(session, workspace_id, note.id, note.content_markdown)

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
    ) -> List[NoteChunk]:
        """Delegate to workspace-scoped semantic vector search."""
        return await search_notes(session, workspace_id, query, limit=limit)

    async def search_fts(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        query: str,
        limit: int = 10,
    ) -> List[NoteSearchResult]:
        """Search notes using PostgreSQL full-text search with ranking."""
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
