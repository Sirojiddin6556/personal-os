"""Tasks domain service with idempotency, optimistic locking, and transactional outbox."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.tasks.enums import TaskStatus
from src.domains.tasks.models import Task
from src.domains.tasks.schemas import (
    KanbanBoardResponse,
    KanbanColumnResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from src.shared.exceptions import NotFoundError, OptimisticLockError
from src.shared.idempotency import idempotency_service
from src.shared.outbox import publish_event


class TaskService:
    """Handles Task operations with concurrency guarantees and event streaming."""

    async def create(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        body: TaskCreate,
        idempotency_key: Optional[str] = None,
    ) -> TaskResponse:
        # 1. Check idempotency key if provided
        if idempotency_key:
            cached = await idempotency_service.get(workspace_id, idempotency_key)
            if cached:
                status_code, body_dict = cached
                return TaskResponse.model_validate(body_dict)

        # 2. Create Task in database
        now = datetime.now(timezone.utc)
        completed_at = now if body.status == TaskStatus.DONE else None
        cancelled_at = now if body.status == TaskStatus.CANCELLED else None

        task = Task(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=body.project_id,
            parent_id=body.parent_id,
            title=body.title,
            description=body.description,
            status=body.status.value,
            priority=body.priority.value,
            due_at=body.due_at,
            estimate_minutes=body.estimate_minutes,
            tracked_seconds=0,
            rank=0,
            version=1,
            waiting_for_reason=body.waiting_for_reason,
            completed_at=completed_at,
            cancelled_at=cancelled_at,
        )
        session.add(task)

        # 3. Publish outbox domain event
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

        # 4. Commit transaction
        await session.commit()
        await session.refresh(task)

        response = TaskResponse.model_validate(task)

        # 5. Cache response in idempotency store
        if idempotency_key:
            await idempotency_service.set(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                status_code=201,
                body=response.model_dump(mode="json"),
            )

        return response

    async def get_by_id(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        task_id: UUID,
    ) -> Task:
        stmt = select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError(resource="Task", identifier=task_id)
        return task

    async def update(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        task_id: UUID,
        body: TaskUpdate,
        version: int,
    ) -> TaskResponse:
        # 1. SELECT FOR UPDATE to acquire row-level lock
        stmt = (
            select(Task)
            .where(Task.id == task_id, Task.workspace_id == workspace_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()

        if not task:
            raise NotFoundError(resource="Task", identifier=task_id)

        # 2. Check optimistic concurrency version
        if task.version != version:
            raise OptimisticLockError(
                resource="Task",
                expected_version=version,
                actual_version=task.version,
            )

        # 3. Update changed attributes
        update_data = body.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)

        if "status" in update_data and update_data["status"] is not None:
            new_status = update_data["status"].value if hasattr(update_data["status"], "value") else str(update_data["status"])
            task.status = new_status
            if new_status == TaskStatus.DONE.value and not task.completed_at:
                task.completed_at = now
            elif new_status != TaskStatus.DONE.value:
                task.completed_at = None

            if new_status == TaskStatus.CANCELLED.value and not task.cancelled_at:
                task.cancelled_at = now
            elif new_status != TaskStatus.CANCELLED.value:
                task.cancelled_at = None

        if "priority" in update_data and update_data["priority"] is not None:
            task.priority = update_data["priority"].value if hasattr(update_data["priority"], "value") else str(update_data["priority"])

        for field in ["title", "description", "project_id", "parent_id", "due_at", "estimate_minutes", "tracked_seconds", "rank", "waiting_for_reason"]:
            if field in update_data:
                setattr(task, field, update_data[field])

        task.version += 1

        # 4. Publish outbox domain event
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
        status: Optional[str] = None,
        project_id: Optional[UUID] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskResponse]:
        stmt = select(Task).where(Task.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Task.status == status)
        if project_id:
            stmt = stmt.where(Task.project_id == project_id)
        if priority:
            stmt = stmt.where(Task.priority == priority)

        stmt = stmt.order_by(Task.rank.asc(), desc(Task.created_at)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        return [TaskResponse.model_validate(t) for t in tasks]

    async def get_kanban_view(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        project_id: Optional[UUID] = None,
    ) -> KanbanBoardResponse:
        """Project tasks into Kanban columns grouped by task status."""
        stmt = (
            select(Task)
            .where(
                Task.workspace_id == workspace_id,
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

    async def delete(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        task_id: UUID,
        version: int,
    ) -> None:
        task = await self.get_by_id(session, workspace_id, task_id)
        if task.version != version:
            raise OptimisticLockError(
                resource="Task",
                expected_version=version,
                actual_version=task.version,
            )

        await session.delete(task)
        await publish_event(
            session=session,
            event_type="task.deleted.v1",
            aggregate_type="task",
            aggregate_id=task_id,
            workspace_id=workspace_id,
            data={"task_id": str(task_id)},
        )
        await session.commit()


task_service = TaskService()
