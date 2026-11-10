"""0010_planner_journal_reminders

The planner models (daily_journals, planner_reminders) were added without a
migration, so on a fresh database the journal and reminder endpoints failed.
Creates both tables (idempotent: IF NOT EXISTS for databases created via
create_all) with tenant RLS, and adds planner_reminders.delivered_at used by
the Telegram reminder dispatcher.

Revision ID: 0010_planner_journal_reminders
Revises: 0009_attachments
Create Date: 2026-11-10 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010_planner_journal_reminders"
down_revision: Union[str, None] = "0009_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = ("daily_journals", "planner_reminders")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_journals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            entry_date DATE NOT NULL,
            morning_intention TEXT,
            gratitude TEXT,
            notes TEXT,
            evening_reflection TEXT,
            mood VARCHAR(30),
            productivity_rating INTEGER,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT uq_daily_journals_workspace_date UNIQUE (workspace_id, entry_date)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_journals_workspace_id ON daily_journals(workspace_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_journals_entry_date ON daily_journals(entry_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS planner_reminders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            remind_at TIMESTAMP WITH TIME ZONE NOT NULL,
            remind_type TEXT NOT NULL DEFAULT 'custom',
            related_id UUID,
            is_dismissed BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp()
        );
    """)
    op.execute("ALTER TABLE planner_reminders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITH TIME ZONE;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_planner_reminders_workspace_id ON planner_reminders(workspace_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_planner_reminders_remind_at ON planner_reminders(remind_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_planner_reminders_is_dismissed ON planner_reminders(is_dismissed);")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_planner_reminders_due
        ON planner_reminders(remind_at) WHERE delivered_at IS NULL AND is_dismissed = false;
    """)

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies WHERE tablename = '{table}' AND policyname = 'tenant_isolation'
                ) THEN
                    CREATE POLICY tenant_isolation ON {table}
                    FOR ALL
                    USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid)
                    WITH CHECK (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
                END IF;
            END $$;
        """)


def downgrade() -> None:
    op.execute("ALTER TABLE planner_reminders DROP COLUMN IF EXISTS delivered_at;")
    op.execute("DROP TABLE IF EXISTS planner_reminders CASCADE;")
    op.execute("DROP TABLE IF EXISTS daily_journals CASCADE;")
