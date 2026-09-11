"""Dashboard aggregation API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.dashboard.schemas import DashboardSummaryResponse, DashboardToday
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


@router.get("/today", response_model=DashboardToday)
async def get_dashboard_today(
    user_tz: str = Query("UTC", description="User IANA timezone name"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
) -> DashboardToday:
    tz = user_tz or getattr(user, "timezone", "UTC")
    return await dashboard_service.get_today(session, workspace.id, tz)
