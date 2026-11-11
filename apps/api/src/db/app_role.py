"""Provision the restricted database role used for tenant-scoped requests.

The owner role from POSTGRES_USER is a superuser in the official image, and
superusers bypass Row Level Security even with FORCE ROW LEVEL SECURITY. API
requests that run inside a workspace therefore connect as a separate role
without SUPERUSER/BYPASSRLS, so the tenant_isolation policies actually apply.
System code (auth, webhooks, background loops) keeps the owner connection.

Run after migrations (docker-entrypoint.sh), using the owner DATABASE_URL:
    APP_DB_USER=personal_os_app APP_DB_PASSWORD=... python -m src.db.app_role
Idempotent: re-applies grants so tables added by new migrations are covered.
"""

import asyncio
import os
import re
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.url import normalize_database_url

_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_SECRET = re.compile(r"^[A-Za-z0-9_\-]{16,128}$")


def build_statements(role: str, password: str, owner: str, database: str) -> list[str]:
    if not _IDENT.match(role) or not _IDENT.match(owner):
        raise ValueError("role names must be lowercase identifiers")
    if not _SECRET.match(password):
        raise ValueError("APP_DB_PASSWORD must be 16-128 chars of [A-Za-z0-9_-] (e.g. openssl rand -hex 32)")
    if role == owner:
        raise ValueError("APP_DB_USER must differ from the owner role")
    db = '"' + database.replace('"', '""') + '"'
    return [
        f"""DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role} LOGIN;
              END IF;
            END $$""",
        f"ALTER ROLE {role} WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE "
        f"NOREPLICATION PASSWORD '{password}'",
        f"GRANT CONNECT ON DATABASE {db} TO {role}",
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
        f"REVOKE ALL ON TABLE alembic_version FROM {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]


async def provision() -> int:
    password = os.getenv("APP_DB_PASSWORD", "").strip()
    if not password:
        print("APP_DB_PASSWORD not set: tenant requests keep the owner connection (RLS not enforced).")
        return 0
    role = os.getenv("APP_DB_USER", "personal_os_app").strip()
    engine = create_async_engine(normalize_database_url(os.environ["DATABASE_URL"]))
    try:
        async with engine.begin() as conn:
            owner = (await conn.execute(text("SELECT current_user"))).scalar_one()
            database = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            for stmt in build_statements(role, password, owner, database):
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()
    print(f"Database role {role!r} ready (no SUPERUSER/BYPASSRLS).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(provision()))
