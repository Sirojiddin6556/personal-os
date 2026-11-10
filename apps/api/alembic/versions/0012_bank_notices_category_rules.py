"""0012_bank_notices_category_rules

Bank card notifications forwarded to the Telegram bot (HUMO / Uzcard) and
learned merchant -> category rules. accounts.card_last4 routes a notice to
the right account.

Revision ID: 0012_bank_notices_category_rules
Revises: 0011_projects_github_columns
Create Date: 2026-11-10 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012_bank_notices_category_rules"
down_revision: Union[str, None] = "0011_projects_github_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = ("bank_notices", "category_rules")


def upgrade() -> None:
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS card_last4 VARCHAR(4);")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE accounts ADD CONSTRAINT chk_accounts_card_last4 CHECK (card_last4 ~ '^[0-9]{4}$');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS bank_notices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            fingerprint TEXT NOT NULL,
            provider TEXT NOT NULL CONSTRAINT chk_bank_notices_provider CHECK (provider IN ('humo','uzcard')),
            kind TEXT NOT NULL CONSTRAINT chk_bank_notices_kind CHECK (kind IN ('income','expense')),
            amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
            currency VARCHAR(3) NOT NULL DEFAULT 'UZS',
            card_last4 VARCHAR(4),
            merchant TEXT NOT NULL DEFAULT '',
            occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CONSTRAINT chk_bank_notices_status CHECK (status IN ('pending','posted','ignored')),
            account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
            transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
            options JSONB NOT NULL DEFAULT '[]'::jsonb,
            auto_rule BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT uq_bank_notices_fingerprint UNIQUE (workspace_id, fingerprint)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_bank_notices_workspace_id ON bank_notices(workspace_id);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS category_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            kind TEXT NOT NULL CONSTRAINT chk_category_rules_kind CHECK (kind IN ('income','expense')),
            category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            confirmations INTEGER NOT NULL DEFAULT 1,
            auto_disabled BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT uq_category_rules_key UNIQUE (workspace_id, key, kind)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_category_rules_workspace_id ON category_rules(workspace_id);")

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
    op.execute("DROP TABLE IF EXISTS category_rules CASCADE;")
    op.execute("DROP TABLE IF EXISTS bank_notices CASCADE;")
    op.execute("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS chk_accounts_card_last4;")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS card_last4;")
