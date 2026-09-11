"""0005_outbox_indexes

Critical performance indexes across all domain modules:
Outbox relay indexes, partial indexes for active tasks, calendar ranges,
financial ledger lookups, notifications, inbox, and Full-Text Search (GIN).

Revision ID: 0005_outbox_indexes
Revises: 0004_partitioned_activity_audit
Create Date: 2026-09-11 10:40:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0005_outbox_indexes"
down_revision: Union[str, None] = "0004_partitioned_activity_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Outbox Relay Critical Indexes
    op.execute("""
        CREATE INDEX idx_outbox_unpublished 
        ON outbox_events (created_at) 
        WHERE published_at IS NULL;
    """)

    op.execute("""
        CREATE INDEX idx_outbox_pending_relay 
        ON outbox_events (created_at ASC) 
        WHERE status = 'pending';
    """)

    op.execute("""
        CREATE INDEX idx_outbox_published_cleanup 
        ON outbox_events (published_at ASC) 
        WHERE status = 'published';
    """)

    # 2. Tasks Domain Indexes
    op.execute("""
        CREATE INDEX idx_tasks_workspace_status 
        ON tasks (workspace_id, status);
    """)

    op.execute("""
        CREATE INDEX idx_tasks_active_due_at 
        ON tasks (workspace_id, due_at ASC) 
        WHERE status NOT IN ('done', 'archived', 'cancelled');
    """)

    op.execute("""
        CREATE INDEX idx_tasks_workspace_project 
        ON tasks (workspace_id, project_id);
    """)

    op.execute("""
        CREATE INDEX idx_tasks_workspace_parent 
        ON tasks (workspace_id, parent_id) 
        WHERE parent_id IS NOT NULL;
    """)

    # 3. Calendar & Timeblocks Indexes
    op.execute("""
        CREATE INDEX idx_events_workspace_range 
        ON events (workspace_id, starts_at, ends_at);
    """)

    op.execute("""
        CREATE INDEX idx_events_workspace_status 
        ON events (workspace_id, status);
    """)

    op.execute("""
        CREATE INDEX idx_time_blocks_workspace_range 
        ON time_blocks (workspace_id, starts_at, ends_at);
    """)

    op.execute("""
        CREATE INDEX idx_time_blocks_task 
        ON time_blocks (task_id) 
        WHERE task_id IS NOT NULL;
    """)

    # 4. Financial Ledger Indexes
    op.execute("""
        CREATE INDEX idx_transactions_workspace_occurred 
        ON transactions (workspace_id, occurred_at DESC);
    """)

    op.execute("""
        CREATE INDEX idx_transactions_account_status 
        ON transactions (account_id, status);
    """)

    op.execute("""
        CREATE INDEX idx_transactions_workspace_category 
        ON transactions (workspace_id, category_id, occurred_at DESC);
    """)

    # 5. Habits Indexes
    op.execute("""
        CREATE INDEX idx_habit_logs_habit_date 
        ON habit_logs (habit_id, logged_date DESC);
    """)

    op.execute("""
        CREATE INDEX idx_habit_logs_workspace_date 
        ON habit_logs (workspace_id, logged_date DESC);
    """)

    # 6. Notifications Indexes
    op.execute("""
        CREATE INDEX idx_notifications_unread 
        ON notifications (workspace_id, user_id, created_at DESC) 
        WHERE read_at IS NULL;
    """)

    op.execute("""
        CREATE INDEX idx_notifications_workspace_status 
        ON notifications (workspace_id, status);
    """)

    # 7. Inbox Items Partial Index
    op.execute("""
        CREATE INDEX idx_inbox_items_pending 
        ON inbox_items (workspace_id, created_at ASC) 
        WHERE status = 'pending';
    """)

    # 8. AI Actions Active Proposed Index
    op.execute("""
        CREATE INDEX idx_ai_actions_active_proposed 
        ON ai_actions (workspace_id, expires_at ASC) 
        WHERE status = 'proposed';
    """)

    # 9. Full-Text Search (GIN)
    op.execute("""
        CREATE INDEX idx_tasks_fts 
        ON tasks 
        USING gin (
            to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(description, ''))
        );
    """)

    op.execute("""
        CREATE INDEX idx_notes_fts 
        ON notes 
        USING gin (
            to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(content_markdown, ''))
        );
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notes_fts;")
    op.execute("DROP INDEX IF EXISTS idx_tasks_fts;")
    op.execute("DROP INDEX IF EXISTS idx_ai_actions_active_proposed;")
    op.execute("DROP INDEX IF EXISTS idx_inbox_items_pending;")
    op.execute("DROP INDEX IF EXISTS idx_notifications_workspace_status;")
    op.execute("DROP INDEX IF EXISTS idx_notifications_unread;")
    op.execute("DROP INDEX IF EXISTS idx_habit_logs_workspace_date;")
    op.execute("DROP INDEX IF EXISTS idx_habit_logs_habit_date;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_workspace_category;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_account_status;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_workspace_occurred;")
    op.execute("DROP INDEX IF EXISTS idx_time_blocks_task;")
    op.execute("DROP INDEX IF EXISTS idx_time_blocks_workspace_range;")
    op.execute("DROP INDEX IF EXISTS idx_events_workspace_status;")
    op.execute("DROP INDEX IF EXISTS idx_events_workspace_range;")
    op.execute("DROP INDEX IF EXISTS idx_tasks_workspace_parent;")
    op.execute("DROP INDEX IF EXISTS idx_tasks_workspace_project;")
    op.execute("DROP INDEX IF EXISTS idx_tasks_active_due_at;")
    op.execute("DROP INDEX IF EXISTS idx_tasks_workspace_status;")
    op.execute("DROP INDEX IF EXISTS idx_outbox_published_cleanup;")
    op.execute("DROP INDEX IF EXISTS idx_outbox_pending_relay;")
    op.execute("DROP INDEX IF EXISTS idx_outbox_unpublished;")
