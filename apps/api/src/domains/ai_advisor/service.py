"""AI Advisor high-level service managing consultations, action confirmations, and rollbacks."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.ai_advisor.models import AIAction, AIPlanUndoLog
from src.domains.ai_advisor.tool_gateway import tool_gateway
from src.domains.tasks.models import Task
from src.domains.tasks.schemas import TaskUpdate
from src.domains.tasks.service import task_service
from src.shared.exceptions import ConflictError, NotFoundError


class AIConsultRequest(BaseModel):
    message: str
    focus_date: Optional[datetime] = None


class AIConsultResponse(BaseModel):
    reply: str
    proposed_actions: List[Dict[str, Any]] = []
    insights: List[str] = []


class AIActionConfirmResponse(BaseModel):
    action_id: UUID
    status: str
    applied_at: datetime


class AIActionUndoResponse(BaseModel):
    action_id: UUID
    status: str
    message: str


class AIAdvisorService:
    """Orchestrates AI advisory consultations, plan approvals, and state rollbacks."""

    async def consult(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        request: AIConsultRequest,
    ) -> AIConsultResponse:
        # Query current workload via safe tool gateway
        tasks = await tool_gateway.get_tasks(session, workspace_id, {"status": "todo", "limit": 10})

        insights = []
        if len(tasks) > 5:
            insights.append("High volume of active todo items detected. Recommend focusing on top 3 priorities.")

        reply = (
            f"Analyzed your schedule and tasks. You currently have {len(tasks)} active tasks in this workspace. "
            "I can assist in scheduling dedicated focus blocks or prioritizing overdue items."
        )

        return AIConsultResponse(
            reply=reply,
            proposed_actions=[],
            insights=insights,
        )

    async def confirm_action(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        action_id: UUID,
    ) -> AIActionConfirmResponse:
        stmt = (
            select(AIAction)
            .where(AIAction.id == action_id, AIAction.workspace_id == workspace_id)
            .with_for_update()
        )
        res = await session.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise NotFoundError(resource="AIAction", identifier=action_id)

        if action.status != "proposed":
            raise ConflictError(
                title="Invalid Action State",
                detail=f"Action '{action_id}' is in status '{action.status}' and cannot be confirmed.",
            )

        now = datetime.now(timezone.utc)
        if action.expires_at < now:
            action.status = "expired"
            await session.commit()
            raise ConflictError(
                title="Action Expired",
                detail=f"Proposal '{action_id}' expired at {action.expires_at.isoformat()}.",
            )

        # Apply action diff
        if action.action_type == "move_task":
            task_id = UUID(action.diff_payload["task_id"])
            changes = action.diff_payload["after"]
            task = await task_service.get_by_id(session, workspace_id, task_id)
            update_req = TaskUpdate.model_validate(changes)
            await task_service.update(
                session=session,
                workspace_id=workspace_id,
                task_id=task_id,
                body=update_req,
                version=task.version,
            )

        action.status = "applied"
        action.applied_at = now
        await session.commit()
        await session.refresh(action)

        return AIActionConfirmResponse(
            action_id=action.id,
            status=action.status,
            applied_at=action.applied_at,
        )

    async def undo_action(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        action_id: UUID,
    ) -> AIActionUndoResponse:
        stmt = (
            select(AIAction)
            .where(AIAction.id == action_id, AIAction.workspace_id == workspace_id)
            .with_for_update()
        )
        res = await session.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise NotFoundError(resource="AIAction", identifier=action_id)

        if action.status != "applied":
            raise ConflictError(
                title="Cannot Undo Action",
                detail=f"Only applied actions can be undone. Current status: '{action.status}'.",
            )

        # Fetch undo log snapshot
        stmt_undo = select(AIPlanUndoLog).where(AIPlanUndoLog.action_id == action_id)
        res_undo = await session.execute(stmt_undo)
        undo_log = res_undo.scalar_one_or_none()

        if not undo_log:
            raise NotFoundError(resource="AIPlanUndoLog", identifier=action_id)

        if action.action_type == "move_task":
            task_id = UUID(action.diff_payload["task_id"])
            original_snapshot = undo_log.entity_snapshots.get("task", {})
            task = await task_service.get_by_id(session, workspace_id, task_id)
            update_req = TaskUpdate(
                title=original_snapshot.get("title"),
                status=original_snapshot.get("status"),
                priority=original_snapshot.get("priority"),
                due_at=original_snapshot.get("due_at"),
            )
            await task_service.update(
                session=session,
                workspace_id=workspace_id,
                task_id=task_id,
                body=update_req,
                version=task.version,
            )

        action.status = "reversed"
        await session.commit()

        return AIActionUndoResponse(
            action_id=action.id,
            status="reversed",
            message="Action successfully rolled back to previous snapshot.",
        )


ai_advisor_service = AIAdvisorService()
