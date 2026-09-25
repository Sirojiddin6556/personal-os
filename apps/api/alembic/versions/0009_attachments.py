"""0009_attachments

Add attachments table for file uploads linked to tasks and projects,
with multi-tenant isolation, foreign keys, and RLS policies.

Revision ID: 0009_attachments
Revises: 0008_reconcile_proj_status
Create Date: 2026-09-17 12:45:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0009_attachments"
down_revision: Union[str, None] = "0008_reconcile_proj_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
            project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_size BIGINT NOT NULL,
            content_type TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_attachments_workspace_id ON attachments(workspace_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_attachments_task_id ON attachments(task_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_attachments_project_id ON attachments(project_id);")

    # RLS policies
    op.execute("ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE attachments FORCE ROW LEVEL SECURITY;")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'attachments' AND policyname = 'tenant_isolation'
            ) THEN
                CREATE POLICY tenant_isolation ON attachments
                FOR ALL
                USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid)
                WITH CHECK (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS attachments CASCADE;")
