"""Normalize DATABASE_URL for SQLAlchemy + asyncpg.

Managed Postgres providers (Neon, Render, Supabase...) hand out libpq-style URLs:
``postgres://user:pw@host/db?sslmode=require&channel_binding=require``.
asyncpg does not understand ``sslmode`` / ``channel_binding`` and the driver
prefix must be ``postgresql+asyncpg://``.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SSL_MODES = {"require", "verify-ca", "verify-full", "prefer", "allow", "disable"}


def normalize_database_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    parts = urlsplit(url)
    if not parts.query:
        return url

    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "channel_binding":
            continue  # libpq-only option
        if key == "sslmode":
            if value in _SSL_MODES and value != "disable":
                query.append(("ssl", "require" if value in ("prefer", "allow") else value))
            continue
        query.append((key, value))
    return urlunsplit(parts._replace(query=urlencode(query)))
