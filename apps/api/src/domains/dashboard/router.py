"""Dashboard aggregation API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.dashboard.schemas import DashboardSummaryResponse
from src.domains.dashboard.service import dashboard_service
from src.domains.identity.models import User, Workspace
from src.shared.deps import get_current_user, get_db_session, get_workspace

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> DashboardSummaryResponse:
    return await dashboard_service.get_summary(session, workspace.id, user.id)
