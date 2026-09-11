"""AI Advisor API endpoints for consultation, tool execution, and action confirmations."""

from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.ai_advisor.service import (
    AIActionConfirmResponse,
    AIActionUndoResponse,
    AIConsultRequest,
    AIConsultResponse,
    ai_advisor_service,
)
from src.domains.identity.models import User, Workspace
from src.shared.deps import get_current_user, get_db_session, get_workspace

router = APIRouter(prefix="/ai", tags=["ai_advisor"])


@router.post("/consult", response_model=AIConsultResponse)
async def consult_ai(
    body: AIConsultRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIConsultResponse:
    return await ai_advisor_service.consult(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        request=body,
    )


@router.post("/actions/{action_id}/confirm", response_model=AIActionConfirmResponse)
async def confirm_action(
    action_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIActionConfirmResponse:
    return await ai_advisor_service.confirm_action(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        action_id=action_id,
    )


@router.post("/actions/{action_id}/undo", response_model=AIActionUndoResponse)
async def undo_action(
    action_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> AIActionUndoResponse:
    return await ai_advisor_service.undo_action(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        action_id=action_id,
    )
