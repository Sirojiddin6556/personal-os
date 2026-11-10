"""0013_integration_providers

integrations.provider / status CHECKs were frozen at the initial schema:
'github' (GitHub import) and 'telegram_user' (bank notices read from the
user's account) were rejected with CheckViolation -> HTTP 500, and so were
the account-login steps 'code_sent' / 'password_needed'.

Revision ID: 0013_integration_providers
Revises: 0012_bank_notices_category_rules
Create Date: 2026-11-10 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013_integration_providers"
down_revision: Union[str, None] = "0012_bank_notices_category_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROVIDERS = ("google_calendar", "telegram", "telegram_user", "github", "discord", "apple_calendar", "notion")
STATUSES = ("connected", "disconnected", "error", "syncing", "code_sent", "password_needed")


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute("ALTER TABLE integrations DROP CONSTRAINT IF EXISTS chk_integrations_provider;")
    op.execute(f"ALTER TABLE integrations ADD CONSTRAINT chk_integrations_provider CHECK (provider IN ({_in(PROVIDERS)}));")
    op.execute("ALTER TABLE integrations DROP CONSTRAINT IF EXISTS chk_integrations_status;")
    op.execute(f"ALTER TABLE integrations ADD CONSTRAINT chk_integrations_status CHECK (status IN ({_in(STATUSES)}));")


def downgrade() -> None:
    op.execute("DELETE FROM integrations WHERE provider IN ('telegram_user', 'github');")
    op.execute("UPDATE integrations SET status = 'error' WHERE status IN ('code_sent', 'password_needed');")
    op.execute("ALTER TABLE integrations DROP CONSTRAINT IF EXISTS chk_integrations_provider;")
    op.execute(
        "ALTER TABLE integrations ADD CONSTRAINT chk_integrations_provider "
        "CHECK (provider IN ('google_calendar', 'telegram', 'discord', 'apple_calendar', 'notion'));"
    )
    op.execute("ALTER TABLE integrations DROP CONSTRAINT IF EXISTS chk_integrations_status;")
    op.execute(
        "ALTER TABLE integrations ADD CONSTRAINT chk_integrations_status "
        "CHECK (status IN ('connected', 'disconnected', 'error', 'syncing'));"
    )
