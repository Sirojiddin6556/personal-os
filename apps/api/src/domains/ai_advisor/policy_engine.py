"""AI Policy Engine enforcing risk tiers and safety constraints on LLM actions."""

from typing import Any, Dict
from src.domains.ai_advisor.tool_gateway import RiskTier, RISK_TIER_INT_MAP
from src.shared.exceptions import ForbiddenError, ValidationDomainError


class PolicyEngine:
    """Enforces 6-tier Risk Governance Model for AI agent actions:

    Tier 1 (Risk 1 / READ): Read-only queries (tasks, free-busy, notes). Auto-approved.
    Tier 2 (Risk 2 / LOW_WRITE): Low-impact mutations (time blocks, adding tags). Auto-approved with undo log.
    Tier 3 (Risk 3 / MEDIUM_WRITE): Medium-impact mutations (rescheduling tasks, updating estimates). Requires preview & confirm.
    Tier 4 (Risk 4 / FINANCIAL): Financial operations (expenses, ledger mutations). Strict modal confirm required.
    Tier 5 (Risk 5 / BULK): Critical batch operations (bulk rescheduling/archiving). Confirmation required.
    Tier 6 (Risk 6 / DESTRUCTIVE): Prohibited operations (direct SQL, deleting accounts/ledgers). Always hard-blocked.
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
        "create_draft_note",
        "add_task_tag",
        "suggest_tags",
    }

    MEDIUM_IMPACT_TOOLS = {
        "create_time_block",
        "move_task",
        "reschedule_task",
        "update_task_priority",
        "create_task",
    }

    FINANCIAL_TOOLS = {
        "post_expense",
        "record_expense",
        "adjust_budget",
    }

    BULK_TOOLS = {
        "bulk_reschedule",
        "bulk_archive_notes",
    }

    HIGH_IMPACT_TOOLS = {
        "cancel_task",
        "cancel_event",
        "delete_note",
    }

    def evaluate_risk_tier(self, tool_name: str, arguments: Dict[str, Any]) -> RiskTier:
        """Return typed RiskTier enum or raise exception if strictly prohibited."""
        if tool_name in self.PROHIBITED_TOOLS:
            raise ForbiddenError(f"Action '{tool_name}' is strictly prohibited by AI Policy Engine (Tier 6: DESTRUCTIVE).")

        # Sanity check for malicious prompt injection substrings
        for key, val in arguments.items():
            if isinstance(val, str):
                low = val.lower()
                if any(inj in low for inj in ["drop table", "select * from users", "exec(", "--", ";--"]):
                    raise ValidationDomainError("Malicious payload pattern detected in tool arguments.")

        if tool_name in self.READ_ONLY_TOOLS:
            return RiskTier.READ
        elif tool_name in self.LOW_IMPACT_TOOLS:
            return RiskTier.LOW_WRITE
        elif tool_name in self.MEDIUM_IMPACT_TOOLS:
            return RiskTier.MEDIUM_WRITE
        elif tool_name in self.FINANCIAL_TOOLS:
            return RiskTier.FINANCIAL
        elif tool_name in self.BULK_TOOLS:
            return RiskTier.BULK
        elif tool_name in self.HIGH_IMPACT_TOOLS:
            return RiskTier.BULK
        else:
            return RiskTier.DESTRUCTIVE

    def evaluate_risk(self, tool_name: str, arguments: Dict[str, Any]) -> int:
        """Return numeric risk tier (1-6) or raise exception if strictly prohibited."""
        tier = self.evaluate_risk_tier(tool_name, arguments)
        return RISK_TIER_INT_MAP[tier]

    def requires_user_confirmation(self, risk_tier: int | RiskTier) -> bool:
        """Determines whether proposal requires explicit human sign-off before applying."""
        if isinstance(risk_tier, RiskTier):
            return risk_tier in (RiskTier.MEDIUM_WRITE, RiskTier.FINANCIAL, RiskTier.BULK, RiskTier.DESTRUCTIVE)
        return risk_tier >= 3


policy_engine = PolicyEngine()
