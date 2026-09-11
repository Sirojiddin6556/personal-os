import os
import uuid
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/personal_os",
)

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "False").lower() in ("true", "1", "yes"),
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def set_tenant_context(session: AsyncSession, workspace_id: uuid.UUID | str) -> None:
    """Set the PostgreSQL session variable for Row Level Security (RLS) tenant isolation.
    
    Using SET LOCAL binds this setting strictly to the current transaction.
    """
    await session.execute(
        text("SET LOCAL app.current_workspace_id = :wid"),
        {"wid": str(workspace_id)},
    )


async def get_session(workspace_id: uuid.UUID) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession with tenant RLS context pre-configured."""
    async with async_session_factory() as session:
        async with session.begin():
            await set_tenant_context(session, workspace_id)
            yield session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession without tenant context (for auth/signup)."""
    async with async_session_factory() as session:
        async with session.begin():
            yield session
