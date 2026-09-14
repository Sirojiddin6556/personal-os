"""0007_external_mappings_project_type

Expand check constraint on external_mappings to support project and repo entity types.

Revision ID: 0007_ext_mappings_proj
Revises: 0006_tasks_is_deleted
Create Date: 2026-09-14 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0007_ext_mappings_proj"
down_revision: Union[str, None] = "0006_tasks_is_deleted"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE external_mappings DROP CONSTRAINT IF EXISTS chk_external_mappings_entity_type;")
    op.execute(
        "ALTER TABLE external_mappings ADD CONSTRAINT chk_external_mappings_entity_type "
        "CHECK (entity_type IN ('event', 'task', 'note', 'transaction', 'channel', 'project', 'repo'));"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE external_mappings DROP CONSTRAINT IF EXISTS chk_external_mappings_entity_type;")
    op.execute(
        "ALTER TABLE external_mappings ADD CONSTRAINT chk_external_mappings_entity_type "
        "CHECK (entity_type IN ('event', 'task', 'note', 'transaction', 'channel'));"
    )
