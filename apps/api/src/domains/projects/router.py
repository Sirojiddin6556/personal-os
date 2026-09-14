"""Projects, Goals and Milestones API routers."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.domains.projects.schemas import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from src.domains.projects.service import project_service
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/projects", tags=["projects"])
goals_router = APIRouter(prefix="/goals", tags=["goals"])
milestones_router = APIRouter(prefix="/milestones", tags=["milestones"])


# Projects
@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> ProjectResponse:
    p = await project_service.create_project(session, workspace.id, body)
    return ProjectResponse.model_validate(p)


@router.get("", response_model=List[ProjectResponse])
@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[ProjectResponse]:
    projects = await project_service.list_projects(session, workspace.id)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> ProjectResponse:
    p = await project_service.get_project(session, workspace.id, project_id)
    return ProjectResponse.model_validate(p)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> ProjectResponse:
    p = await project_service.update_project(session, workspace.id, project_id, body)
    return ProjectResponse.model_validate(p)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await project_service.delete_project(session, workspace.id, project_id)


# Goals
@goals_router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
@goals_router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> GoalResponse:
    g = await project_service.create_goal(session, workspace.id, body)
    return GoalResponse.model_validate(g)


@goals_router.get("", response_model=List[GoalResponse])
@goals_router.get("/", response_model=List[GoalResponse])
async def list_goals(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[GoalResponse]:
    goals = await project_service.list_goals(session, workspace.id)
    return [GoalResponse.model_validate(g) for g in goals]


@goals_router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> GoalResponse:
    goal = await project_service.get_goal(session, workspace.id, goal_id)
    return GoalResponse.model_validate(goal)


@goals_router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    body: GoalUpdate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> GoalResponse:
    goal = await project_service.update_goal(session, workspace.id, goal_id, body)
    return GoalResponse.model_validate(goal)


@goals_router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await project_service.delete_goal(session, workspace.id, goal_id)


# Milestones
@milestones_router.post("", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED)
@milestones_router.post("/", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED)
async def create_milestone(
    body: MilestoneCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> MilestoneResponse:
    m = await project_service.create_milestone(session, workspace.id, body)
    return MilestoneResponse.model_validate(m)


@milestones_router.get("", response_model=List[MilestoneResponse])
@milestones_router.get("/", response_model=List[MilestoneResponse])
async def list_milestones(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[MilestoneResponse]:
    milestones = await project_service.list_milestones(session, workspace.id)
    return [MilestoneResponse.model_validate(m) for m in milestones]


@milestones_router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone(
    milestone_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> MilestoneResponse:
    m = await project_service.get_milestone(session, workspace.id, milestone_id)
    return MilestoneResponse.model_validate(m)


@milestones_router.patch("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    milestone_id: UUID,
    body: MilestoneUpdate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> MilestoneResponse:
    m = await project_service.update_milestone(session, workspace.id, milestone_id, body)
    return MilestoneResponse.model_validate(m)


@milestones_router.delete("/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_milestone(
    milestone_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await project_service.delete_milestone(session, workspace.id, milestone_id)

