"""Tasks and Kanban API endpoints."""

from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.domains.tasks.schemas import (
    AttachmentResponse,
    KanbanBoardResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from src.domains.tasks.service import task_service
from src.shared.deps import get_db_session, get_workspace, parse_etag
from src.shared.pagination import CursorPage

router = APIRouter(prefix="/tasks", tags=["tasks"])
kanban_router = APIRouter(prefix="/kanban", tags=["kanban"])
attachments_router = APIRouter(prefix="/attachments", tags=["attachments"])

UPLOAD_DIR = Path("data/uploads")



@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task with Idempotency-Key",
)
@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task with Idempotency-Key",
)
async def create_task(
    body: TaskCreate,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TaskResponse:
    created = await task_service.create(
        session=session,
        workspace_id=workspace.id,
        body=body,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = f'"{created.version}"'
    return created


@router.get(
    "",
    response_model=CursorPage[TaskResponse],
    summary="List workspace tasks with cursor pagination and filters",
)
@router.get(
    "/",
    response_model=CursorPage[TaskResponse],
    summary="List workspace tasks with cursor pagination and filters",
)
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by task status"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    cursor: Optional[str] = Query(None, description="Opaque cursor for pagination offset"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> CursorPage[TaskResponse]:
    return await task_service.list_tasks(
        session=session,
        workspace_id=workspace.id,
        status=status,
        project_id=project_id,
        priority=priority,
        cursor=cursor,
        limit=limit,
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
    if_match: Optional[str] = Header(None, alias="If-Match"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TaskResponse:
    # ETag version parsing (raises 428 if missing, 400 if malformed)
    version = parse_etag(if_match)
    updated = await task_service.update(
        session=session,
        task_id=task_id,
        workspace_id=workspace.id,
        body=body,
        version=version,
    )
    response.headers["ETag"] = f'"{updated.version}"'
    return updated


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete task with optional optimistic locking (If-Match ETag)",
)
async def delete_task(
    task_id: UUID,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Response:
    # soft delete
    version = parse_etag(if_match) if if_match else None
    await task_service.delete(
        session=session,
        workspace_id=workspace.id,
        task_id=task_id,
        version=version,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{task_id}/complete",
    response_model=TaskResponse,
    summary="Explicitly transition task to DONE status",
)
async def complete_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TaskResponse:
    return await task_service.complete_task(
        session=session,
        workspace_id=workspace.id,
        task_id=task_id,
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


# Attachments
@router.post(
    "/{task_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and attach a file to a task",
)
async def upload_task_attachment(
    task_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> AttachmentResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Имя файла не указано")

    ws_dir = UPLOAD_DIR / str(workspace.id)
    ws_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix
    safe_filename = f"{uuid4()}{ext}"
    dest_path = ws_dir / safe_filename

    max_bytes = 50 * 1024 * 1024  # 50 MB
    size = 0

    try:
        with open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 64):
                size += len(chunk)
                if size > max_bytes:
                    buffer.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Размер файла превышает лимит 50 МБ",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сохранения файла: {str(e)}",
        )

    content_type = file.content_type or "application/octet-stream"
    return await task_service.add_attachment(
        session=session,
        workspace_id=workspace.id,
        task_id=task_id,
        filename=file.filename,
        stored_filename=str(dest_path),
        file_size=size,
        content_type=content_type,
    )


@router.get(
    "/{task_id}/attachments",
    response_model=List[AttachmentResponse],
    summary="List all attachments for a task",
)
async def list_task_attachments(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[AttachmentResponse]:
    return await task_service.list_attachments(
        session=session,
        workspace_id=workspace.id,
        task_id=task_id,
    )


@attachments_router.get(
    "/{attachment_id}/download",
    summary="Download attachment file",
)
async def download_attachment(
    attachment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> FileResponse:
    attachment = await task_service.get_attachment(session, workspace.id, attachment_id)
    file_path = Path(attachment.stored_filename)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден на сервере")
    return FileResponse(
        path=str(file_path),
        filename=attachment.filename,
        media_type=attachment.content_type,
    )


@attachments_router.get(
    "",
    response_model=List[AttachmentResponse],
    summary="List attachments by workspace, project, or task",
)
async def list_attachments(
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    task_id: Optional[UUID] = Query(None, description="Filter by task ID"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[AttachmentResponse]:
    return await task_service.list_attachments(
        session=session,
        workspace_id=workspace.id,
        project_id=project_id,
        task_id=task_id,
    )


@attachments_router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete attachment",
)
async def delete_attachment(
    attachment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await task_service.delete_attachment(session, workspace.id, attachment_id)


