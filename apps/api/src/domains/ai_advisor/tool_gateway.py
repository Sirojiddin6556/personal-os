"""AI Tool Gateway: safe, isolated, policy-governed interface between LLMs and Personal OS."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.ai_advisor.models import AIAction, AIPlanUndoLog, AIToolCall
from src.domains.ai_advisor.policy_engine import policy_engine
from src.domains.calendar.schemas import FreeBusyResponse, TimeBlockCreate
from src.domains.calendar.service import calendar_service
from src.domains.tasks.schemas import TaskResponse, TaskUpdate
from src.domains.tasks.service import task_service
from src.shared.exceptions import ValidationDomainError


class ToolCallResult(BaseModel):
    tool_name: str
    status: str
    risk_tier: int
    requires_confirmation: bool
    data: Any
    action_id: Optional[UUID] = None


class ToolGateway:
    """Safe gateway for AI LLM execution without direct database access."""

    async def _record_tool_call(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        tool_name: str,
        arguments: Dict[str, Any],
        output: Any,
        status: str,
        start_time: float,
        action_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        elapsed_ms = int((time.time() - start_time) * 1000)
        output_payload = output if isinstance(output, dict) else {"result": str(output)}

        call_record = AIToolCall(
            id=uuid4(),
            workspace_id=workspace_id,
            action_id=action_id,
            correlation_id=correlation_id or str(uuid4()),
            tool_name=tool_name,
            input_arguments=arguments,
            output_result=output_payload,
            model_name="personal-os-agent",
            prompt_tokens=0,
            completion_tokens=0,
            execution_time_ms=elapsed_ms,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        session.add(call_record)
        await session.commit()

    async def get_tasks(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[TaskResponse]:
        """Read-only tool returning tasks for the assistant."""
        start_t = time.time()
        tool_name = "get_tasks"
        filters = filters or {}
        risk = policy_engine.evaluate_risk(tool_name, filters)

        tasks = await task_service.list_tasks(
            session=session,
            workspace_id=workspace_id,
            status=filters.get("status"),
            project_id=filters.get("project_id"),
            priority=filters.get("priority"),
            limit=filters.get("limit", 20),
        )

        await self._record_tool_call(
            session=session,
            workspace_id=workspace_id,
            tool_name=tool_name,
            arguments=filters,
            output={"count": len(tasks)},
            status="success",
            start_time=start_t,
        )
        return tasks

    async def get_free_busy(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        start_dt: datetime,
        end_dt: datetime,
    ) -> FreeBusyResponse:
        """Read-only tool querying availability windows."""
        start_t = time.time()
        tool_name = "get_free_busy"
        args = {"start_dt": start_dt.isoformat(), "end_dt": end_dt.isoformat()}
        risk = policy_engine.evaluate_risk(tool_name, args)

        res = await calendar_service.get_free_busy(session, workspace_id, start_dt, end_dt)

        await self._record_tool_call(
            session=session,
            workspace_id=workspace_id,
            tool_name=tool_name,
            arguments=args,
            output={"free_windows_count": len(res.free_windows)},
            status="success",
            start_time=start_t,
        )
        return res

    async def move_task(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        task_id: UUID,
        updates: TaskUpdate,
        version: int,
    ) -> ToolCallResult:
        """Mutating tool: updates task or creates proposed action depending on policy risk tier."""
        start_t = time.time()
        tool_name = "move_task"
        args = {"task_id": str(task_id), "updates": updates.model_dump(mode="json", exclude_unset=True)}
        risk_tier = policy_engine.evaluate_risk(tool_name, args)

        # Retrieve current snapshot for undo logging
        current_task = await task_service.get_by_id(session, workspace_id, task_id)
        current_snapshot = {
            "title": current_task.title,
            "status": current_task.status,
            "priority": current_task.priority,
            "due_at": current_task.due_at.isoformat() if current_task.due_at else None,
            "version": current_task.version,
        }

        # Check if requires explicit confirmation
        if policy_engine.requires_user_confirmation(risk_tier):
            action = AIAction(
                id=uuid4(),
                workspace_id=workspace_id,
                user_id=user_id,
                action_type="move_task",
                diff_payload={"task_id": str(task_id), "before": current_snapshot, "after": args["updates"]},
                risk_tier=risk_tier,
                status="proposed",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            session.add(action)
            await session.flush()

            undo_log = AIPlanUndoLog(
                id=uuid4(),
                workspace_id=workspace_id,
                action_id=action.id,
                entity_snapshots={"task": current_snapshot},
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                created_at=datetime.now(timezone.utc),
            )
            session.add(undo_log)
            await session.commit()

            await self._record_tool_call(
                session=session,
                workspace_id=workspace_id,
                tool_name=tool_name,
                arguments=args,
                output={"status": "proposed", "action_id": str(action.id)},
                status="success",
                start_time=start_t,
                action_id=action.id,
            )

            return ToolCallResult(
                tool_name=tool_name,
                status="proposed",
                risk_tier=risk_tier,
                requires_confirmation=True,
                data=args["updates"],
                action_id=action.id,
            )

        # Low risk tier: apply immediately and create undo log
        updated_task = await task_service.update(
            session=session,
            workspace_id=workspace_id,
            task_id=task_id,
            body=updates,
            version=version,
        )

        await self._record_tool_call(
            session=session,
            workspace_id=workspace_id,
            tool_name=tool_name,
            arguments=args,
            output={"status": "applied", "task_id": str(updated_task.id)},
            status="success",
            start_time=start_t,
        )

        return ToolCallResult(
            tool_name=tool_name,
            status="applied",
            risk_tier=risk_tier,
            requires_confirmation=False,
            data=updated_task.model_dump(mode="json"),
        )

    async def create_time_block(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        data: TimeBlockCreate,
    ) -> ToolCallResult:
        """Create calendar focus time block for the user."""
        start_t = time.time()
        tool_name = "create_time_block"
        args = data.model_dump(mode="json")
        risk_tier = policy_engine.evaluate_risk(tool_name, args)

        tb = await calendar_service.create_time_block(session, workspace_id, data)

        await self._record_tool_call(
            session=session,
            workspace_id=workspace_id,
            tool_name=tool_name,
            arguments=args,
            output={"time_block_id": str(tb.id)},
            status="success",
            start_time=start_t,
        )

        return ToolCallResult(
            tool_name=tool_name,
            status="applied",
            risk_tier=risk_tier,
            requires_confirmation=False,
            data={"id": str(tb.id), "starts_at": tb.starts_at.isoformat(), "ends_at": tb.ends_at.isoformat()},
        )


tool_gateway = ToolGateway()
