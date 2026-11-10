"""0011_projects_github_columns

Project.github_repo / github_default_branch exist in the model (GitHub import)
but were never migrated: creating or listing projects failed with
UndefinedColumnError on a database built from migrations.

Revision ID: 0011_projects_github_columns
Revises: 0010_planner_journal_reminders
Create Date: 2026-11-10 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011_projects_github_columns"
down_revision: Union[str, None] = "0010_planner_journal_reminders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS github_repo TEXT;")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS github_default_branch TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS github_default_branch;")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS github_repo;")
