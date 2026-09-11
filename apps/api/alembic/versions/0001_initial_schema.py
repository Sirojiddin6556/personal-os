"""0001_initial_schema

Initial baseline database schema migration for Personal OS.
Creates extensions (pgcrypto, vector, uuid-ossp, btree_gist),
core helper functions, and all 30+ relational domain tables with
strict CHECK constraints, FK cascades, and defaults.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-11 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gist"')

    # 2. Universal updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = clock_timestamp();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 3. Helper function for RLS workspace session resolution
    op.execute("""
        CREATE OR REPLACE FUNCTION current_workspace_id()
        RETURNS UUID AS $$
        BEGIN
            RETURN NULLIF(current_setting('app.current_workspace_id', true), '')::uuid;
        EXCEPTION
            WHEN OTHERS THEN
                RETURN NULL;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)

    # 4. Global Users table (Non-tenant scoped)
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="UTC"),
        sa.Column("locale", sa.String(length=10), nullable=False, server_default="ru"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name="chk_users_email_format"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="chk_users_status"),
    )

    # 5. Workspaces table (Tenants)
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False, server_default="free"),
        sa.Column("plan_tier", sa.Text(), nullable=False, server_default="free"),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("plan_tier IN ('free', 'pro', 'team', 'enterprise')", name="chk_workspaces_plan_tier"),
        sa.CheckConstraint("slug ~* '^[a-z0-9-]+$'", name="chk_workspaces_slug_format"),
    )

    # 6. Memberships table
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="member"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_memberships_workspace_user"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="chk_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'invited', 'suspended')", name="chk_memberships_status"),
    )

    # 7. Goals table
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="general"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('active', 'completed', 'paused', 'archived')", name="chk_goals_status"),
        sa.CheckConstraint("progress_percentage BETWEEN 0 AND 100", name="chk_goals_progress"),
    )

    # 8. Projects table
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=False, server_default="#3B82F6"),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('active', 'completed', 'on_hold', 'archived')", name="chk_projects_status"),
        sa.CheckConstraint("color ~* '^#[0-9A-Fa-f]{6}$'", name="chk_projects_color"),
    )

    # 9. Milestones table
    op.create_table(
        "milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('pending', 'achieved', 'missed')", name="chk_milestones_status"),
    )

    # 10. Tasks table
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="inbox"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("estimate_minutes", sa.Integer(), nullable=True),
        sa.Column("tracked_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("waiting_for_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint(
            "status IN ('inbox', 'todo', 'scheduled', 'in_progress', 'waiting', 'done', 'cancelled', 'archived')",
            name="chk_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical', 'P1', 'P2', 'P3', 'P4')",
            name="chk_tasks_priority",
        ),
        sa.CheckConstraint("estimate_minutes IS NULL OR estimate_minutes > 0", name="chk_tasks_estimate_positive"),
        sa.CheckConstraint("tracked_seconds >= 0", name="chk_tasks_tracked_positive"),
        sa.CheckConstraint("status != 'done' OR completed_at IS NOT NULL", name="chk_tasks_done_completed_at"),
        sa.CheckConstraint("status != 'cancelled' OR cancelled_at IS NOT NULL", name="chk_tasks_cancelled_cancelled_at"),
        sa.CheckConstraint("status != 'waiting' OR waiting_for_reason IS NOT NULL", name="chk_tasks_waiting_reason"),
    )

    # 11. Events table
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="confirmed"),
        sa.Column("sync_status", sa.Text(), nullable=False, server_default="local"),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("external_etag", sa.Text(), nullable=True),
        sa.Column("recurrence_rule", sa.Text(), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("ends_at >= starts_at", name="chk_events_chronology"),
        sa.CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name="chk_events_status"),
        sa.CheckConstraint(
            "sync_status IN ('local', 'sync_pending', 'synced', 'remote_changed', 'conflict', 'delete_pending', 'deleted', 'sync_failed')",
            name="chk_events_sync_status",
        ),
    )

    # 12. Time blocks table
    op.create_table(
        "time_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("is_fixed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("ends_at > starts_at", name="chk_time_blocks_chronology"),
    )

    # 13. Accounts table
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default="checking"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("initial_balance_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("current_balance_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint(
            "type IN ('checking', 'savings', 'credit_card', 'cash', 'investment', 'crypto')",
            name="chk_accounts_type",
        ),
        sa.CheckConstraint("length(currency) = 3", name="chk_accounts_currency"),
    )

    # 14. Categories table
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=False, server_default="#10B981"),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("type IN ('income', 'expense', 'transfer')", name="chk_categories_type"),
        sa.CheckConstraint("color ~* '^#[0-9A-Fa-f]{6}$'", name="chk_categories_color"),
    )

    # 15. Transactions table (Immutable financial ledger)
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("destination_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reversed_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("posted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("amount_minor > 0", name="chk_transactions_amount_positive"),
        sa.CheckConstraint("type IN ('income', 'expense', 'transfer', 'reversal')", name="chk_transactions_type"),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_review', 'posted', 'reversed', 'rejected')",
            name="chk_transactions_status",
        ),
        sa.CheckConstraint("type != 'transfer' OR destination_account_id IS NOT NULL", name="chk_transactions_transfer_destination"),
        sa.CheckConstraint("type != 'transfer' OR account_id != destination_account_id", name="chk_transactions_transfer_different_accounts"),
        sa.CheckConstraint("type != 'reversal' OR reversed_transaction_id IS NOT NULL", name="chk_transactions_reversal_ref"),
        sa.CheckConstraint("status NOT IN ('posted', 'reversed') OR posted_at IS NOT NULL", name="chk_transactions_posted_timestamp"),
    )

    # 16. Budgets table
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("period_type", sa.Text(), nullable=False, server_default="monthly"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("amount_minor > 0", name="chk_budgets_amount_positive"),
        sa.CheckConstraint("period_type IN ('weekly', 'monthly', 'quarterly', 'yearly')", name="chk_budgets_period_type"),
    )

    # 17. Budget periods table
    op.create_table(
        "budget_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("spent_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("budget_id", "start_date", name="uq_budget_periods_budget_start"),
        sa.CheckConstraint("end_date >= start_date", name="chk_budget_periods_dates"),
        sa.CheckConstraint("spent_minor >= 0", name="chk_budget_periods_spent_positive"),
    )

    # 18. Notes table
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )

    # 19. Note chunks table (vector 1536 dim)
    op.execute("""
        CREATE TABLE note_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            chunk_index INT NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            token_count INT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT uq_note_chunks_note_index UNIQUE (note_id, chunk_index),
            CONSTRAINT chk_note_chunks_token_count CHECK (token_count > 0)
        );
    """)

    # 20. Habits table
    op.create_table(
        "habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency_type", sa.Text(), nullable=False, server_default="daily"),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("frequency_type IN ('daily', 'weekdays', 'weekends', 'weekly')", name="chk_habits_frequency"),
        sa.CheckConstraint("target_count > 0", name="chk_habits_target_positive"),
        sa.CheckConstraint("current_streak >= 0 AND best_streak >= current_streak", name="chk_habits_streaks_positive"),
    )

    # 21. Habit logs table
    op.create_table(
        "habit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("habit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logged_date", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("habit_id", "logged_date", name="uq_habit_logs_habit_date"),
        sa.CheckConstraint("count > 0", name="chk_habit_logs_count_positive"),
    )

    # 22. Integrations table
    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="connected"),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint(
            "provider IN ('google_calendar', 'telegram', 'discord', 'apple_calendar', 'notion')",
            name="chk_integrations_provider",
        ),
        sa.CheckConstraint("status IN ('connected', 'disconnected', 'error', 'syncing')", name="chk_integrations_status"),
    )

    # 23. OAuth credentials table (AES-256-GCM BYTEA isolated)
    op.create_table(
        "oauth_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("encrypted_access_token", postgresql.BYTEA(), nullable=False),
        sa.Column("iv_access", postgresql.BYTEA(), nullable=False),
        sa.Column("tag_access", postgresql.BYTEA(), nullable=False),
        sa.Column("encrypted_refresh_token", postgresql.BYTEA(), nullable=True),
        sa.Column("iv_refresh", postgresql.BYTEA(), nullable=True),
        sa.Column("tag_refresh", postgresql.BYTEA(), nullable=True),
        sa.Column("token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("key_version > 0", name="chk_oauth_credentials_key_version"),
    )

    # 24. External mappings table
    op.create_table(
        "external_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("internal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("sync_hash", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("integration_id", "entity_type", "external_id", name="uq_external_mappings_lookup"),
        sa.CheckConstraint("entity_type IN ('event', 'task', 'note', 'transaction', 'channel')", name="chk_external_mappings_entity_type"),
    )

    # 25. Webhook subscriptions table
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_channel_id", sa.Text(), nullable=False),
        sa.Column("external_resource_id", sa.Text(), nullable=True),
        sa.Column("client_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("provider", "external_channel_id", name="uq_webhook_subscriptions_provider_channel"),
    )

    # 26. Sync states table
    op.create_table(
        "sync_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("sync_token", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="synced"),
        sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("integration_id", "provider", name="uq_sync_states_integration_provider"),
        sa.CheckConstraint("status IN ('synced', 'full_sync_in_progress', 'error')", name="chk_sync_states_status"),
    )

    # 27. Inbox items table (Quick capture)
    op.create_table(
        "inbox_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="web"),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("parsed_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("processed_entity_type", sa.Text(), nullable=True),
        sa.Column("processed_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint(
            "source IN ('web', 'telegram', 'mobile', 'api', 'extension', 'email')",
            name="chk_inbox_items_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'discarded', 'failed')",
            name="chk_inbox_items_status",
        ),
        sa.CheckConstraint(
            "(status != 'processed') OR (processed_entity_type IS NOT NULL AND processed_entity_id IS NOT NULL)",
            name="chk_inbox_items_processed_pair",
        ),
    )

    # 28. Outbox events table (Transactional Outbox)
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('pending', 'processing', 'published', 'failed')", name="chk_outbox_status"),
        sa.CheckConstraint("retry_count >= 0 AND retry_count <= max_retries + 5", name="chk_outbox_retries"),
    )

    # 29. Activity events table (Partitioned base table)
    op.execute("""
        CREATE TABLE activity_events (
            id UUID DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            actor_id UUID,
            actor_type TEXT NOT NULL DEFAULT 'user',
            event_type TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id UUID NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (id, occurred_at),
            CONSTRAINT chk_activity_actor_type CHECK (actor_type IN ('user', 'system', 'ai', 'integration'))
        ) PARTITION BY RANGE (occurred_at);
    """)

    # 30. Audit logs table (Partitioned base table)
    op.execute("""
        CREATE TABLE audit_logs (
            id UUID DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            actor_id UUID,
            actor_type TEXT NOT NULL DEFAULT 'user',
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id UUID NOT NULL,
            client_ip INET,
            user_agent TEXT,
            prev_entry_hash TEXT,
            entry_hash TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (id, occurred_at),
            CONSTRAINT chk_audit_actor_type CHECK (actor_type IN ('user', 'system', 'ai', 'integration'))
        ) PARTITION BY RANGE (occurred_at);
    """)

    # 31. Notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False, server_default="in_app"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="normal"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("channel IN ('in_app', 'telegram', 'email', 'push')", name="chk_notifications_channel"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="chk_notifications_priority"),
        sa.CheckConstraint("status IN ('pending', 'delivered', 'read', 'failed')", name="chk_notifications_status"),
    )

    # 32. Delivery attempts table
    op.create_table(
        "delivery_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="initiated"),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("channel IN ('in_app', 'telegram', 'email', 'push')", name="chk_delivery_attempts_channel"),
        sa.CheckConstraint("status IN ('initiated', 'success', 'failed')", name="chk_delivery_attempts_status"),
    )

    # 33. AI actions table
    op.create_table(
        "ai_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("diff_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_tier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("risk_tier BETWEEN 1 AND 6", name="chk_ai_actions_risk_tier"),
        sa.CheckConstraint(
            "status IN ('proposed', 'confirmed', 'rejected', 'applied', 'failed', 'expired')",
            name="chk_ai_actions_status",
        ),
        sa.CheckConstraint("status != 'applied' OR applied_at IS NOT NULL", name="chk_ai_actions_applied_timestamp"),
    )

    # 34. AI tool calls table
    op.create_table(
        "ai_tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_actions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("input_arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('success', 'error', 'timeout', 'blocked')", name="chk_ai_tool_calls_status"),
    )

    # 35. AI plan undo logs table
    op.create_table(
        "ai_plan_undo_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_actions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("entity_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )

    # 36. Attach updated_at triggers to all tables with updated_at column
    mutable_tables = [
        "users", "workspaces", "memberships", "goals", "projects", "milestones",
        "tasks", "events", "time_blocks", "accounts", "categories", "transactions",
        "budgets", "budget_periods", "notes", "note_chunks", "habits", "habit_logs",
        "integrations", "oauth_credentials", "external_mappings", "webhook_subscriptions",
        "sync_states", "inbox_items", "outbox_events", "notifications", "ai_actions",
    ]
    for tbl in mutable_tables:
        op.execute(f"""
            CREATE TRIGGER trg_set_updated_at_{tbl}
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    tables_to_drop = [
        "ai_plan_undo_logs", "ai_tool_calls", "ai_actions", "delivery_attempts",
        "notifications", "audit_logs", "activity_events", "outbox_events", "inbox_items",
        "sync_states", "webhook_subscriptions", "external_mappings", "oauth_credentials",
        "integrations", "habit_logs", "habits", "note_chunks", "notes", "budget_periods",
        "budgets", "transactions", "categories", "accounts", "time_blocks", "events",
        "tasks", "milestones", "projects", "goals", "memberships", "workspaces", "users",
    ]
    for tbl in tables_to_drop:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")

    op.execute("DROP FUNCTION IF EXISTS current_workspace_id CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;")
