"""0008_reconciliation_and_project_statuses

Expand check constraint on transactions to support reconciliation type,
expand check constraint on projects to support planning status,
and harmonize check constraint on goals to support planning, active, on_hold, completed, archived.

NOTE: Schema downgrade is supported, but data normalization (paused -> on_hold) is irreversible.

Revision ID: 0008_reconcile_proj_status
Revises: 0007_ext_mappings_proj
Create Date: 2026-09-14 11:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0008_reconcile_proj_status"
down_revision: Union[str, None] = "0007_ext_mappings_proj"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Transactions check constraint
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_type;")
    op.execute(
        "ALTER TABLE transactions ADD CONSTRAINT chk_transactions_type "
        "CHECK (type IN ('income', 'expense', 'transfer', 'reversal', 'reconciliation'));"
    )

    # 2. Projects check constraint
    op.execute("ALTER TABLE projects DROP CONSTRAINT IF EXISTS chk_projects_status;")
    op.execute(
        "ALTER TABLE projects ADD CONSTRAINT chk_projects_status "
        "CHECK (status IN ('planning', 'active', 'on_hold', 'completed', 'archived'));"
    )

    # 3. Goals check constraint (drop old constraint first to allow on_hold updates)
    op.execute("ALTER TABLE goals DROP CONSTRAINT IF EXISTS chk_goals_status;")
    op.execute("UPDATE goals SET status = 'on_hold' WHERE status = 'paused';")
    op.execute(
        "ALTER TABLE goals ADD CONSTRAINT chk_goals_status "
        "CHECK (status IN ('planning', 'active', 'on_hold', 'completed', 'archived'));"
    )



def downgrade() -> None:
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_type;")
    op.execute(
        "ALTER TABLE transactions ADD CONSTRAINT chk_transactions_type "
        "CHECK (type IN ('income', 'expense', 'transfer', 'reversal'));"
    )
    op.execute("ALTER TABLE projects DROP CONSTRAINT IF EXISTS chk_projects_status;")
    op.execute(
        "ALTER TABLE projects ADD CONSTRAINT chk_projects_status "
        "CHECK (status IN ('active', 'completed', 'on_hold', 'archived'));"
    )
    op.execute("ALTER TABLE goals DROP CONSTRAINT IF EXISTS chk_goals_status;")
    op.execute(
        "ALTER TABLE goals ADD CONSTRAINT chk_goals_status "
        "CHECK (status IN ('active', 'completed', 'paused', 'archived'));"
    )

