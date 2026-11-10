import pytest

from src.db.url import normalize_database_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        (
            "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb?ssl=require",
        ),
        ("postgresql://u:p@h/db?sslmode=disable", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql://u:p@h/db?application_name=x", "postgresql+asyncpg://u:p@h/db?application_name=x"),
    ],
)
def test_normalize(raw, expected):
    assert normalize_database_url(raw) == expected
