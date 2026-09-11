"""0006_tasks_is_deleted

Add is_deleted column to tasks table with index for multi-tenant soft delete.

Revision ID: 0006_tasks_is_deleted
Revises: 0005_outbox_indexes
Create Date: 2026-09-11 11:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006_tasks_is_deleted"
down_revision: Union[str, None] = "0005_outbox_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_tasks_workspace_is_deleted",
        "tasks",
        ["workspace_id", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_workspace_is_deleted", table_name="tasks")
    op.drop_column("tasks", "is_deleted")
