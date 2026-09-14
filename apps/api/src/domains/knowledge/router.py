"""Knowledge API endpoints for Notes and Full-Text Search."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.domains.knowledge.schemas import (
    NoteCreate,
    NoteResponse,
    NoteSearchResult,
    NoteUpdate,
)
from src.domains.knowledge.service import knowledge_service
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> NoteResponse:
    note = await knowledge_service.create_note(session, workspace.id, body)
    return NoteResponse.model_validate(note)


@router.get("/notes", response_model=List[NoteResponse])
async def list_notes(
    is_pinned: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[NoteResponse]:
    notes = await knowledge_service.list_notes(session, workspace.id, is_pinned, limit, offset)
    return [NoteResponse.model_validate(n) for n in notes]


@router.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> NoteResponse:
    note = await knowledge_service.get_note(session, workspace.id, note_id)
    return NoteResponse.model_validate(note)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    body: NoteUpdate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> NoteResponse:
    note = await knowledge_service.update_note(session, workspace.id, note_id, body)
    return NoteResponse.model_validate(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await knowledge_service.delete_note(session, workspace.id, note_id)



@router.get("/search", response_model=List[NoteSearchResult])
async def search_notes(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[NoteSearchResult]:
    return await knowledge_service.search_fts(session, workspace.id, q, limit)
