"""AI Policy Engine enforcing risk tiers and safety constraints on LLM actions."""

from typing import Any, Dict
from src.shared.exceptions import ForbiddenError, ValidationDomainError


class PolicyEngine:
    """Enforces 6-tier Risk Governance Model for AI agent actions:

    Tier 1 (Risk 1): Read-only queries (tasks, free-busy, notes). Auto-approved.
    Tier 2 (Risk 2): Low-impact mutations (time blocks, adding tags). Auto-approved with undo log.
    Tier 3 (Risk 3): Medium-impact mutations (rescheduling tasks, updating estimates). Requires confirmation.
    Tier 4 (Risk 4): High-impact mutations (cancelling tasks, modifying events). Explicit confirmation required.
    Tier 5 (Risk 5): Critical operations (bulk modifications). Re-authentication required.
    Tier 6 (Risk 6): Prohibited operations (direct SQL, deleting accounts/ledgers). Always blocked.
    """

    PROHIBITED_TOOLS = {
        "execute_sql",
        "drop_table",
        "delete_workspace",
        "delete_financial_ledger",
        "export_all_credentials",
    }

    READ_ONLY_TOOLS = {
        "get_tasks",
        "get_free_busy",
        "search_notes",
        "get_dashboard_summary",
        "get_project_progress",
    }

    LOW_IMPACT_TOOLS = {
        "create_time_block",
        "add_task_tag",
        "create_draft_note",
    }

    MEDIUM_IMPACT_TOOLS = {
        "move_task",
        "reschedule_task",
        "update_task_priority",
    }

    HIGH_IMPACT_TOOLS = {
        "cancel_task",
        "cancel_event",
        "delete_note",
    }

    def evaluate_risk(self, tool_name: str, arguments: Dict[str, Any]) -> int:
        """Return numeric risk tier (1-6) or raise exception if strictly prohibited."""
        if tool_name in self.PROHIBITED_TOOLS:
            raise ForbiddenError(f"Action '{tool_name}' is strictly prohibited by AI Policy Engine (Tier 6).")

        # Sanity check for malicious prompt injection substrings
        for key, val in arguments.items():
            if isinstance(val, str):
                low = val.lower()
                if "drop table" in low or "select * from users" in low or "exec(" in low:
                    raise ValidationDomainError("Malicious payload pattern detected in tool arguments.")

        if tool_name in self.READ_ONLY_TOOLS:
            return 1
        elif tool_name in self.LOW_IMPACT_TOOLS:
            return 2
        elif tool_name in self.MEDIUM_IMPACT_TOOLS:
            return 3
        elif tool_name in self.HIGH_IMPACT_TOOLS:
            return 4
        else:
            # Unknown tool defaults to Tier 4
            return 4

    def requires_user_confirmation(self, risk_tier: int) -> bool:
        """Determines whether proposal requires explicit human sign-off before applying."""
        return risk_tier >= 3


policy_engine = PolicyEngine()
