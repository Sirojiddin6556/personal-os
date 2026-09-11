"""AI Advisor REST API endpoints for Quick Add, Planner, RAG, Morning Brief, and Confirmation."""

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.ai_advisor import service as ai_service
from src.domains.ai_advisor.schemas import (
    AIActionConfirmResponse,
    AIActionUndoResponse,
    AIConsultRequest,
    AIConsultResponse,
    AIPreviewPlan,
    MorningBriefResponse,
    NoteChunkResponse,
    ParseRequest,
    ParseResponse,
    PlanRequest,
    RAGQARequest,
    RAGQAResponse,
    SearchRequest,
)
from src.domains.identity.models import User, Workspace
from src.domains.knowledge import service as knowledge_service
from src.shared.deps import get_current_user, get_db_session, get_workspace

# Root router encompassing both /advisor and /ai namespaces for forward/backward compatibility
router = APIRouter(tags=["ai-advisor"])
advisor_router = APIRouter(prefix="/advisor", tags=["ai-advisor"])
ai_router = APIRouter(prefix="/ai", tags=["ai-advisor"])


# =============================================================================
# QUICK ADD PARSER
# =============================================================================
@advisor_router.post("/parse", response_model=ParseResponse)
async def parse_input_endpoint(
    body: ParseRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> ParseResponse:
    """Extract structured intent and entity fields from raw text."""
    result = await ai_service.parse_input(
        text=body.text,
        workspace_id=workspace.id,
        session=session,
        actor_id=user.id,
    )
    return ParseResponse(**result.model_dump())


# =============================================================================
# SCHEDULE PLANNER
# =============================================================================
@advisor_router.post("/plans", response_model=AIPreviewPlan, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIPreviewPlan:
    """Generate optimized schedule plan returning a preview diff for human confirmation."""
    plan = await ai_service.create_plan(
        workspace_id=workspace.id,
        request=body.request,
        session=session,
        actor_id=user.id,
    )
    return plan


@advisor_router.post("/plans/{plan_id}/apply")
async def apply_plan(
    plan_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Atomically apply all confirmed modifications from a proposed plan."""
    await ai_service.apply_plan(
        plan_id=plan_id,
        workspace_id=workspace.id,
        session=session,
        actor_id=user.id,
    )
    return {"status": "applied"}


# =============================================================================
# RAG SEMANTIC VECTOR SEARCH & Q&A
# =============================================================================
@advisor_router.post("/search-notes", response_model=List[NoteChunkResponse])
async def search_notes(
    body: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[NoteChunkResponse]:
    """Execute workspace-isolated semantic vector search over knowledge chunks."""
    chunks = await knowledge_service.search_notes(
        session=session,
        workspace_id=workspace.id,
        query=body.query,
        limit=body.limit,
    )
    return [NoteChunkResponse.model_validate(c) for c in chunks]


@advisor_router.post("/rag-qa", response_model=RAGQAResponse)
async def rag_question_answer(
    body: RAGQARequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> RAGQAResponse:
    """Answer questions grounded on personal knowledge base notes."""
    return await ai_service.rag_qa(
        workspace_id=workspace.id,
        question=body.question,
        session=session,
        limit_sources=body.limit_sources,
        actor_id=user.id,
    )


# =============================================================================
# MORNING BRIEF
# =============================================================================
@advisor_router.get("/brief", response_model=MorningBriefResponse)
@advisor_router.post("/brief", response_model=MorningBriefResponse)
async def get_morning_brief(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> MorningBriefResponse:
    """Retrieve executive morning briefing for the day."""
    return await ai_service.generate_morning_brief(
        workspace_id=workspace.id,
        session=session,
        actor_id=user.id,
    )


# =============================================================================
# BACKWARD-COMPATIBLE /ai NAMESPACE ROUTES
# =============================================================================
@ai_router.post("/parse", response_model=ParseResponse)
async def parse_input_ai_alias(
    body: ParseRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> ParseResponse:
    return await parse_input_endpoint(body, session, workspace, user)


@ai_router.post("/plans", response_model=AIPreviewPlan, status_code=status.HTTP_201_CREATED)
async def create_plan_ai_alias(
    body: PlanRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIPreviewPlan:
    return await create_plan(body, session, workspace, user)


@ai_router.post("/plans/{plan_id}/apply")
async def apply_plan_ai_alias(
    plan_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    return await apply_plan(plan_id, session, workspace, user)


@ai_router.post("/search-notes", response_model=List[NoteChunkResponse])
async def search_notes_ai_alias(
    body: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[NoteChunkResponse]:
    return await search_notes(body, session, workspace)


@ai_router.post("/consult", response_model=AIConsultResponse)
async def consult_ai(
    body: AIConsultRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIConsultResponse:
    return await ai_service.ai_advisor_service.consult(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        request=body,
    )


@ai_router.post("/actions/{action_id}/confirm", response_model=AIActionConfirmResponse)
async def confirm_action(
    action_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIActionConfirmResponse:
    return await ai_service.ai_advisor_service.confirm_action(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        action_id=action_id,
    )


@ai_router.post("/actions/{action_id}/undo", response_model=AIActionUndoResponse)
async def undo_action(
    action_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIActionUndoResponse:
    return await ai_service.ai_advisor_service.undo_action(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        action_id=action_id,
    )


# Attach sub-routers
router.include_router(advisor_router)
router.include_router(ai_router)
