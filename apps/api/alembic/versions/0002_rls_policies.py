"""0002_rls_policies

Row Level Security (RLS) policies with FORCE ROW LEVEL SECURITY on all
tenant tables, financial ledger immutability trigger, and note chunk workspace integrity.

Revision ID: 0002_rls_policies
Revises: 0001_initial_schema
Create Date: 2026-09-11 10:10:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002_rls_policies"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "memberships",
    "goals",
    "projects",
    "milestones",
    "tasks",
    "events",
    "time_blocks",
    "accounts",
    "categories",
    "transactions",
    "budgets",
    "budget_periods",
    "notes",
    "note_chunks",
    "habits",
    "habit_logs",
    "integrations",
    "oauth_credentials",
    "external_mappings",
    "webhook_subscriptions",
    "sync_states",
    "inbox_items",
    "activity_events",
    "audit_logs",
    "outbox_events",
    "notifications",
    "delivery_attempts",
    "ai_actions",
    "ai_tool_calls",
    "ai_plan_undo_logs",
]


def upgrade() -> None:
    # 1. Enable and Force Row Level Security on all tenant-scoped tables
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid)
            WITH CHECK (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
        """)

    # 2. Immutability trigger for financial transactions (DOM-001 / DOM-002 / DOM-003)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_posted_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('posted', 'reversed') THEN
                    RAISE EXCEPTION 'Cannot delete a posted or reversed transaction (id=%). Create a reversal instead.', OLD.id
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN OLD;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF OLD.status = 'posted' THEN
                    IF NEW.status = 'reversed' AND
                       NEW.amount_minor = OLD.amount_minor AND
                       NEW.currency = OLD.currency AND
                       NEW.account_id = OLD.account_id AND
                       NEW.occurred_at = OLD.occurred_at THEN
                        RETURN NEW;
                    ELSE
                        RAISE EXCEPTION 'Cannot modify a posted transaction (id=%). Create a reversal instead.', OLD.id
                            USING ERRCODE = 'integrity_constraint_violation';
                    END IF;
                END IF;

                IF OLD.status = 'reversed' THEN
                    RAISE EXCEPTION 'Cannot modify a reversed transaction (id=%).', OLD.id
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_prevent_posted_mutation
        BEFORE UPDATE OR DELETE ON transactions
        FOR EACH ROW EXECUTE FUNCTION prevent_posted_mutation();
    """)

    # 3. Workspace integrity trigger for note_chunks (DOM-004 / DOM-005)
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_note_chunk_workspace()
        RETURNS TRIGGER AS $$
        DECLARE
            parent_workspace_id UUID;
        BEGIN
            SELECT workspace_id INTO parent_workspace_id 
            FROM notes 
            WHERE id = NEW.note_id;

            IF parent_workspace_id IS NULL THEN
                RAISE EXCEPTION 'Parent note id=% not found for chunk.', NEW.note_id
                    USING ERRCODE = 'foreign_key_violation';
            END IF;

            IF parent_workspace_id != NEW.workspace_id THEN
                RAISE EXCEPTION 'Tenant violation: note chunk workspace_id (%) does not match parent note (%).',
                    NEW.workspace_id, parent_workspace_id
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_validate_note_chunk_workspace
        BEFORE INSERT OR UPDATE ON note_chunks
        FOR EACH ROW EXECUTE FUNCTION validate_note_chunk_workspace();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_validate_note_chunk_workspace ON note_chunks;")
    op.execute("DROP FUNCTION IF EXISTS validate_note_chunk_workspace CASCADE;")

    op.execute("DROP TRIGGER IF EXISTS trg_prevent_posted_mutation ON transactions;")
    op.execute("DROP FUNCTION IF EXISTS prevent_posted_mutation CASCADE;")

    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
