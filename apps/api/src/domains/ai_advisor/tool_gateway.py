"""AI Tool Gateway: typed, isolated, policy-governed interface between LLMs and Personal OS."""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.ai_advisor.models import AIToolCall
from src.domains.calendar.schemas import TimeBlockCreate
from src.domains.calendar.service import calendar_service
from src.domains.finance.schemas import TransactionCreate
from src.domains.finance.service import finance_service
from src.domains.tasks.schemas import TaskCreate, TaskUpdate
from src.domains.tasks.service import task_service
from src.shared.exceptions import ForbiddenError, NotFoundError, ValidationDomainError


class RiskTier(str, Enum):
    """6-tier Risk Governance Model for AI agent operations."""

    READ = "read"
    LOW_WRITE = "low_write"
    MEDIUM_WRITE = "medium_write"
    FINANCIAL = "financial"
    BULK = "bulk"
    DESTRUCTIVE = "destructive"


# Numeric mapping for database check constraints (1 to 6)
RISK_TIER_INT_MAP: Dict[RiskTier, int] = {
    RiskTier.READ: 1,
    RiskTier.LOW_WRITE: 2,
    RiskTier.MEDIUM_WRITE: 3,
    RiskTier.FINANCIAL: 4,
    RiskTier.BULK: 5,
    RiskTier.DESTRUCTIVE: 6,
}


@dataclass
class ToolCall:
    tool_name: str
    risk_tier: RiskTier
    args: Dict[str, Any]


class ToolGateway:
    """Safe gateway executing typed operations for LLMs without direct database access."""

    TOOL_REGISTRY: Dict[str, RiskTier] = {
        # READ TOOLS
        "get_tasks": RiskTier.READ,
        "get_free_busy": RiskTier.READ,
        "search_notes": RiskTier.READ,
        # LOW_WRITE TOOLS
        "create_draft_note": RiskTier.LOW_WRITE,
        "add_task_tag": RiskTier.LOW_WRITE,
        # MEDIUM_WRITE TOOLS
        "move_task": RiskTier.MEDIUM_WRITE,
        "create_time_block": RiskTier.MEDIUM_WRITE,
        "create_task": RiskTier.MEDIUM_WRITE,
        "reschedule_task": RiskTier.MEDIUM_WRITE,
        # FINANCIAL TOOLS
        "post_expense": RiskTier.FINANCIAL,
        "record_expense": RiskTier.FINANCIAL,
        # BULK TOOLS
        "bulk_reschedule": RiskTier.BULK,
        "bulk_archive_notes": RiskTier.BULK,
        # DESTRUCTIVE TOOLS (Hard-Blocked)
        "execute_sql": RiskTier.DESTRUCTIVE,
        "drop_table": RiskTier.DESTRUCTIVE,
        "delete_workspace": RiskTier.DESTRUCTIVE,
        "delete_financial_ledger": RiskTier.DESTRUCTIVE,
        "export_all_credentials": RiskTier.DESTRUCTIVE,
    }

    def __init__(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        actor_id: Optional[UUID] = None,
    ):
        self.session = session
        self.workspace_id = workspace_id
        self.actor_id = actor_id or uuid4()

    # -------------------------------------------------------------------------
    # AUDIT LOGGING
    # -------------------------------------------------------------------------
    async def _log_tool_call(
        self,
        name: str,
        risk: RiskTier,
        args: Dict[str, Any],
        output: Any = None,
        status: str = "success",
        execution_time_ms: int = 0,
        action_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Record telemetry and audit trail in ai_tool_calls table."""
        output_payload = output if isinstance(output, dict) else ({"result": output} if output is not None else None)

        record = AIToolCall(
            id=uuid4(),
            workspace_id=self.workspace_id,
            action_id=action_id,
            correlation_id=correlation_id or str(uuid4()),
            tool_name=name,
            input_arguments=args,
            output_result=output_payload,
            model_name="personal-os-tool-gateway",
            prompt_tokens=0,
            completion_tokens=0,
            execution_time_ms=execution_time_ms,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        # Flush to register in transaction without prematurely terminating caller transaction
        await self.session.flush()

    # -------------------------------------------------------------------------
    # READ TOOLS (Risk: READ -> auto-approved)
    # -------------------------------------------------------------------------
    async def get_tasks(
        self,
        status: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Read-only tool returning tasks for the current workspace."""
        t0 = time.time()
        tasks = await task_service.list_tasks(
            session=self.session,
            workspace_id=self.workspace_id,
            filters={"status": status},
            limit=limit,
        )
        elapsed_ms = int((time.time() - t0) * 1000)

        # Handle CursorPage or list of items
        items = tasks.items if hasattr(tasks, "items") else tasks
        result = [t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t) for t in items]

        await self._log_tool_call(
            name="get_tasks",
            risk=RiskTier.READ,
            args={"status": status, "limit": limit},
            output={"count": len(result)},
            status="success",
            execution_time_ms=elapsed_ms,
        )
        return result

    async def get_free_busy(self, date: str) -> List[Dict[str, Any]]:
        """Read-only tool querying events and calendar free/busy slots."""
        t0 = time.time()
        events = await calendar_service.get_events_for_day(self.session, self.workspace_id, date)
        elapsed_ms = int((time.time() - t0) * 1000)

        await self._log_tool_call(
            name="get_free_busy",
            risk=RiskTier.READ,
            args={"date": date},
            output={"events_count": len(events)},
            status="success",
            execution_time_ms=elapsed_ms,
        )
        return events

    async def search_notes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Read-only semantic vector search over knowledge notes."""
        from src.domains.knowledge.service import search_notes as rag_search_notes

        t0 = time.time()
        chunks = await rag_search_notes(self.session, self.workspace_id, query, limit=limit)
        elapsed_ms = int((time.time() - t0) * 1000)

        result = [
            {
                "chunk_id": str(c.id),
                "note_id": str(c.note_id),
                "chunk_index": c.chunk_index,
                "content": c.content,
                "token_count": c.token_count,
            }
            for c in chunks
        ]

        await self._log_tool_call(
            name="search_notes",
            risk=RiskTier.READ,
            args={"query": query, "limit": limit},
            output={"chunks_found": len(result)},
            status="success",
            execution_time_ms=elapsed_ms,
        )
        return result

    # -------------------------------------------------------------------------
    # MEDIUM WRITE TOOLS (Risk: MEDIUM_WRITE -> requires preview confirmation)
    # -------------------------------------------------------------------------
    async def move_task(
        self,
        task_id: str,
        new_status: str,
        scheduled_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Propose task relocation or status change with confirmation required."""
        payload = {
            "tool_name": "move_task",
            "task_id": task_id,
            "new_status": new_status,
            "scheduled_at": scheduled_at,
            "requires_confirmation": True,
        }
        await self._log_tool_call("move_task", RiskTier.MEDIUM_WRITE, {"task_id": task_id, "status": new_status, "scheduled_at": scheduled_at}, output=payload)
        return payload

    async def create_time_block(
        self,
        task_id: str,
        start_at: str,
        end_at: str,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Propose focus time block creation with confirmation required."""
        payload = {
            "tool_name": "create_time_block",
            "task_id": task_id,
            "start_at": start_at,
            "end_at": end_at,
            "label": label or "Focus Block",
            "requires_confirmation": True,
        }
        await self._log_tool_call("create_time_block", RiskTier.MEDIUM_WRITE, payload, output=payload)
        return payload

    async def create_task(
        self,
        title: str,
        priority: str = "medium",
        due_at: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Propose task creation with confirmation required."""
        payload = {
            "tool_name": "create_task",
            "title": title,
            "priority": priority,
            "due_at": due_at,
            "description": description,
            "requires_confirmation": True,
        }
        await self._log_tool_call("create_task", RiskTier.MEDIUM_WRITE, payload, output=payload)
        return payload

    # -------------------------------------------------------------------------
    # FINANCIAL TOOLS (Risk: FINANCIAL -> strictly requires modal confirmation)
    # -------------------------------------------------------------------------
    async def post_expense(
        self,
        amount_minor: int,
        currency: str,
        category: str,
        account_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Propose financial expense ledger posting with strict human confirmation."""
        payload = {
            "tool_name": "post_expense",
            "amount_minor": amount_minor,
            "currency": currency.upper(),
            "category": category,
            "account_id": account_id,
            "note": note,
            "requires_confirmation": True,
        }
        await self._log_tool_call("post_expense", RiskTier.FINANCIAL, payload, output=payload)
        return payload

    # -------------------------------------------------------------------------
    # DISPATCH & EXECUTION ENGINE
    # -------------------------------------------------------------------------
    def evaluate_risk(self, tool_name: str, args: Dict[str, Any]) -> RiskTier:
        """Determine risk tier and guard against SQL/Command injection."""
        tier = self.TOOL_REGISTRY.get(tool_name, RiskTier.DESTRUCTIVE)

        # Check for malicious SQL or command injection patterns in arguments
        for k, v in args.items():
            if isinstance(v, str):
                low = v.lower()
                if any(inj in low for inj in ["drop table", "select * from", "delete from", "--", ";--", "exec("]):
                    raise ValidationDomainError(f"Prohibited pattern detected in tool parameter '{k}'.")

        return tier

    async def dispatch(self, tool_call: Any) -> Dict[str, Any]:
        """Dispatch a tool call request through the policy gate."""
        if hasattr(tool_call, "name") and hasattr(tool_call, "args"):
            name = tool_call.name
            args = tool_call.args
        elif isinstance(tool_call, dict):
            name = tool_call.get("tool_name") or tool_call.get("name")
            args = tool_call.get("args") or tool_call.get("parameters") or {}
        else:
            raise ValidationDomainError("Invalid tool call specification format.")

        risk_tier = self.evaluate_risk(name, args)

        # DESTRUCTIVE tier is strictly hard-blocked
        if risk_tier == RiskTier.DESTRUCTIVE:
            await self._log_tool_call(
                name=name,
                risk=RiskTier.DESTRUCTIVE,
                args=args,
                output={"error": "Action hard-blocked by policy"},
                status="blocked",
            )
            raise ForbiddenError(f"Action '{name}' is categorized as DESTRUCTIVE and is strictly prohibited.")

        # Route by tool name
        if name == "get_tasks":
            return {"tool_name": name, "result": await self.get_tasks(**args)}
        elif name == "get_free_busy":
            date_arg = args.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            return {"tool_name": name, "result": await self.get_free_busy(date=date_arg)}
        elif name == "search_notes":
            return {"tool_name": name, "result": await self.search_notes(**args)}
        elif name == "move_task":
            return await self.move_task(**args)
        elif name == "create_time_block":
            return await self.create_time_block(**args)
        elif name == "create_task":
            return await self.create_task(**args)
        elif name in ("post_expense", "record_expense"):
            return await self.post_expense(**args)
        else:
            # Generic fallback: proposal requiring confirmation
            payload = {"tool_name": name, "args": args, "requires_confirmation": True}
            await self._log_tool_call(name, risk_tier, args, output=payload)
            return payload

    async def apply_confirmed(self, change: Dict[str, Any]) -> Any:
        """Atomically apply a confirmed tool modification to domain services."""
        tool_name = change.get("tool_name") or change.get("name")

        if tool_name == "move_task":
            task_id = UUID(change["task_id"])
            current_task = await task_service.get_by_id(self.session, self.workspace_id, task_id)

            update_data = {
                "status": change.get("new_status") or change.get("status"),
            }
            if change.get("scheduled_at"):
                update_data["due_at"] = datetime.fromisoformat(change["scheduled_at"].replace("Z", "+00:00"))

            updated = await task_service.update(
                session=self.session,
                workspace_id=self.workspace_id,
                task_id=task_id,
                body=TaskUpdate(**update_data),
                version=current_task.version,
            )
            return updated

        elif tool_name == "create_time_block":
            task_id = UUID(change["task_id"]) if change.get("task_id") else None
            start_str = change["start_at"].replace("Z", "+00:00")
            end_str = change["end_at"].replace("Z", "+00:00")
            starts_at = datetime.fromisoformat(start_str)
            ends_at = datetime.fromisoformat(end_str)

            tb = await calendar_service.create_time_block(
                session=self.session,
                workspace_id=self.workspace_id,
                body=TimeBlockCreate(
                    task_id=task_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    label=change.get("label") or "Focus Block",
                ),
            )
            return tb

        elif tool_name in ("post_expense", "record_expense"):
            account_id = UUID(change["account_id"])
            tx = await finance_service.post_transaction(
                session=self.session,
                workspace_id=self.workspace_id,
                body=TransactionCreate(
                    account_id=account_id,
                    amount_minor=int(change["amount_minor"]),
                    currency=change.get("currency", "USD"),
                    type="expense",
                    note=change.get("note") or f"Expense for {change.get('category', 'miscellaneous')}",
                ),
            )
            return tx

        elif tool_name == "create_task":
            due_at = None
            if change.get("due_at"):
                due_at = datetime.fromisoformat(change["due_at"].replace("Z", "+00:00"))

            task = await task_service.create(
                session=self.session,
                workspace_id=self.workspace_id,
                body=TaskCreate(
                    title=change["title"],
                    description=change.get("description"),
                    priority=change.get("priority", "medium"),
                    due_at=due_at,
                ),
            )
            return task

        else:
            raise ValidationDomainError(f"Cannot apply unknown tool change: '{tool_name}'")


# Singleton-compatible default instance
tool_gateway = ToolGateway(session=None, workspace_id=uuid4())  # type: ignore
