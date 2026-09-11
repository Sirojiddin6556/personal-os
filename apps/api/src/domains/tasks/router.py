"""Tasks and Kanban API endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.domains.tasks.schemas import (
    KanbanBoardResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from src.domains.tasks.service import task_service
from src.shared.deps import get_db_session, get_workspace, parse_etag

router = APIRouter(prefix="/tasks", tags=["tasks"])
kanban_router = APIRouter(prefix="/kanban", tags=["kanban"])


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task with Idempotency-Key",
)
async def create_task(
    body: TaskCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TaskResponse:
    return await task_service.create(
        session=session,
        workspace_id=workspace.id,
        body=body,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/",
    response_model=List[TaskResponse],
    summary="List workspace tasks with optional filters",
)
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by task status"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[TaskResponse]:
    return await task_service.list_tasks(
        session=session,
        workspace_id=workspace.id,
        status=status,
        project_id=project_id,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Retrieve task by ID with ETag version",
)
async def get_task(
    task_id: UUID,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TaskResponse:
    task = await task_service.get_by_id(session, workspace.id, task_id)
    response.headers["ETag"] = f'"{task.version}"'
    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update task with optimistic locking (If-Match ETag)",
)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    response: Response,
    if_match: str = Header(..., alias="If-Match"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TaskResponse:
    version = parse_etag(if_match)
    updated = await task_service.update(
        session=session,
        workspace_id=workspace.id,
        task_id=task_id,
        body=body,
        version=version,
    )
    response.headers["ETag"] = f'"{updated.version}"'
    return updated


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete task with optimistic locking (If-Match ETag)",
)
async def delete_task(
    task_id: UUID,
    if_match: str = Header(..., alias="If-Match"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    version = parse_etag(if_match)
    await task_service.delete(
        session=session,
        workspace_id=workspace.id,
        task_id=task_id,
        version=version,
    )


@kanban_router.get(
    "/",
    response_model=KanbanBoardResponse,
    summary="Retrieve tasks grouped into Kanban status columns",
)
async def get_kanban(
    project_id: Optional[UUID] = Query(None, description="Optional project filter"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> KanbanBoardResponse:
    return await task_service.get_kanban_view(
        session=session,
        workspace_id=workspace.id,
        project_id=project_id,
    )
