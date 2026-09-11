"""Tasks domain service with idempotency, optimistic locking, and transactional outbox."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.tasks.models import Priority, Task, TaskStatus
from src.domains.tasks.schemas import (
    KanbanBoardResponse,
    KanbanColumnResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from src.shared.exceptions import ConflictError, NotFoundError, OptimisticLockError
from src.shared.idempotency import idempotency_service
from src.shared.outbox import publish_event
from src.shared.pagination import CursorPage, decode_cursor, encode_cursor


class TaskService:
    """Handles Task operations with concurrency guarantees, cursor pagination, and event streaming."""

    async def create(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        body: TaskCreate,
        idempotency_key: Optional[str] = None,
        redis: Any = None,
    ) -> TaskResponse:
        # 1. Проверить idempotency_key в Redis (SETNX, TTL 24h)
        if idempotency_key:
            cached = await idempotency_service.get(workspace_id, idempotency_key)
            if cached:
                status_code, body_dict = cached
                return TaskResponse.model_validate(body_dict)

        now = datetime.now(timezone.utc)
        status_val = body.status or TaskStatus.INBOX.value
        completed_at = now if status_val == TaskStatus.DONE.value else None

        # 2. INSERT Task
        task = Task(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=body.project_id,
            parent_id=body.parent_id,
            title=body.title,
            description=body.description,
            status=status_val,
            priority=body.priority or Priority.MEDIUM.value,
            due_at=body.due_at,
            estimate_minutes=body.estimate_minutes,
            tracked_seconds=0,
            rank=0,
            version=1,
            is_deleted=False,
            waiting_for_reason=body.waiting_for_reason,
            completed_at=completed_at,
            cancelled_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(task)

        # 3. publish_event(session, 'task.created.v1', workspace_id, task.id, ...)
        await publish_event(
            session=session,
            event_type="task.created.v1",
            aggregate_type="task",
            aggregate_id=task.id,
            workspace_id=workspace_id,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
            },
        )

        # 4. await session.commit()
        await session.commit()
        await session.refresh(task)

        response = TaskResponse.model_validate(task)

        # 5. Сохранить idempotency result в Redis
        if idempotency_key:
            await idempotency_service.set(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                status_code=201,
                body=response.model_dump(mode="json"),
                ttl_seconds=86400,
            )

        return response

    async def get_by_id(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        task_id: UUID,
    ) -> Task:
        stmt = select(Task).where(
            Task.id == task_id,
            Task.workspace_id == workspace_id,
            Task.is_deleted.is_(False),
        )
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError(resource="Task", identifier=task_id)
        return task

    async def update(
        self,
        session: AsyncSession,
        task_id: UUID,
        workspace_id: UUID,
        body: TaskUpdate,
        version: int,
    ) -> TaskResponse:
        # SELECT ... FOR UPDATE
        stmt = (
            select(Task)
            .where(
                Task.id == task_id,
                Task.workspace_id == workspace_id,
                Task.is_deleted.is_(False),
            )
            .with_for_update()
        )
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()

        if not task:
            raise NotFoundError(resource="Task", identifier=task_id)

        if task.version != version:
            raise ConflictError(
                title="Optimistic Lock Conflict",
                detail=f"Task version conflict: client provided version {version}, current database version is {task.version}.",
            )

        update_data = body.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)

        # Валидация state machine переходов
        if "status" in update_data and update_data["status"] is not None:
            new_status = (
                update_data["status"].value
                if hasattr(update_data["status"], "value")
                else str(update_data["status"])
            )
            task.status = new_status
            if new_status == TaskStatus.DONE.value:
                task.completed_at = now
            elif new_status != TaskStatus.DONE.value:
                task.completed_at = None

            if new_status == TaskStatus.CANCELLED.value:
                task.cancelled_at = now
            elif new_status != TaskStatus.CANCELLED.value:
                task.cancelled_at = None

        if "priority" in update_data and update_data["priority"] is not None:
            task.priority = (
                update_data["priority"].value
                if hasattr(update_data["priority"], "value")
                else str(update_data["priority"])
            )

        for field in [
            "title",
            "description",
            "project_id",
            "parent_id",
            "due_at",
            "estimate_minutes",
            "tracked_seconds",
            "rank",
            "waiting_for_reason",
        ]:
            if field in update_data:
                setattr(task, field, update_data[field])

        # Обновить поля & version
        task.version += 1

        # publish_event + commit
        await publish_event(
            session=session,
            event_type="task.updated.v1",
            aggregate_type="task",
            aggregate_id=task.id,
            workspace_id=workspace_id,
            data={
                "task_id": str(task.id),
                "version": task.version,
                "status": task.status,
                "priority": task.priority,
            },
        )

        await session.commit()
        await session.refresh(task)
        return TaskResponse.model_validate(task)

    async def list_tasks(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
        status: Optional[str] = None,
        project_id: Optional[UUID] = None,
        priority: Optional[str] = None,
    ) -> CursorPage[TaskResponse]:
        # WHERE workspace_id=... AND is_deleted=false + фильтры
        filters = filters or {}
        filter_status = status or filters.get("status")
        filter_project = project_id or filters.get("project_id")
        filter_priority = priority or filters.get("priority")
        page_limit = limit or filters.get("limit", 50)
        page_cursor = cursor or filters.get("cursor")

        stmt = select(Task).where(
            Task.workspace_id == workspace_id,
            Task.is_deleted.is_(False),
        )

        if filter_status:
            stmt = stmt.where(Task.status == filter_status)
        if filter_project:
            stmt = stmt.where(Task.project_id == filter_project)
        if filter_priority:
            stmt = stmt.where(Task.priority == filter_priority)

        # cursor-based pagination по (updated_at, id)
        if page_cursor:
            decoded = decode_cursor(page_cursor)
            if decoded and "updated_at" in decoded and "id" in decoded:
                c_updated_at = datetime.fromisoformat(decoded["updated_at"])
                c_id = UUID(decoded["id"])
                stmt = stmt.where(
                    (Task.updated_at < c_updated_at)
                    | ((Task.updated_at == c_updated_at) & (Task.id < c_id))
                )

        stmt = (
            stmt.order_by(desc(Task.updated_at), desc(Task.id))
            .limit(page_limit + 1)
        )
        result = await session.execute(stmt)
        tasks = list(result.scalars().all())

        has_more = len(tasks) > page_limit
        items_to_return = tasks[:page_limit] if has_more else tasks

        next_cursor = None
        if has_more and items_to_return:
            last = items_to_return[-1]
            next_cursor = encode_cursor({
                "updated_at": last.updated_at.isoformat(),
                "id": str(last.id),
            })

        return CursorPage[TaskResponse](
            items=[TaskResponse.model_validate(t) for t in items_to_return],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def delete(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        task_id: UUID,
        version: Optional[int] = None,
    ) -> None:
        # Soft delete
        stmt = (
            select(Task)
            .where(
                Task.id == task_id,
                Task.workspace_id == workspace_id,
                Task.is_deleted.is_(False),
            )
            .with_for_update()
        )
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            raise NotFoundError(resource="Task", identifier=task_id)

        if version is not None and task.version != version:
            raise ConflictError(
                title="Optimistic Lock Conflict",
                detail=f"Task version conflict: expected {version}, found {task.version}.",
            )

        task.is_deleted = True
        task.version += 1

        await publish_event(
            session=session,
            event_type="task.deleted.v1",
            aggregate_type="task",
            aggregate_id=task.id,
            workspace_id=workspace_id,
            data={"task_id": str(task.id)},
        )
        await session.commit()

    async def get_kanban_view(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        project_id: Optional[UUID] = None,
    ) -> KanbanBoardResponse:
        """Project active tasks into Kanban columns grouped by task status."""
        stmt = (
            select(Task)
            .where(
                Task.workspace_id == workspace_id,
                Task.is_deleted.is_(False),
                Task.status.notin_([TaskStatus.ARCHIVED.value]),
            )
        )
        if project_id:
            stmt = stmt.where(Task.project_id == project_id)

        stmt = stmt.order_by(Task.rank.asc(), desc(Task.created_at))
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        column_keys = [
            TaskStatus.INBOX.value,
            TaskStatus.TODO.value,
            TaskStatus.SCHEDULED.value,
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.WAITING.value,
            TaskStatus.DONE.value,
        ]

        grouped: Dict[str, List[TaskResponse]] = {col: [] for col in column_keys}
        for t in tasks:
            if t.status in grouped:
                grouped[t.status].append(TaskResponse.model_validate(t))

        columns = {
            col: KanbanColumnResponse(
                status=col,
                count=len(grouped[col]),
                tasks=grouped[col],
            )
            for col in column_keys
        }

        return KanbanBoardResponse(columns=columns)


task_service = TaskService()
