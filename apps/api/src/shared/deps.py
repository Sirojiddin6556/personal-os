"""FastAPI dependency injection providers for authentication, tenant context, and database sessions."""

import re
from typing import AsyncGenerator, Optional
from uuid import UUID

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import async_session_factory, get_session as get_tenant_db_session
from src.domains.identity.models import Membership, User, Workspace
from src.shared.exceptions import (
    ForbiddenError,
    PreconditionFailedError,
    UnauthorizedError,
)


def parse_etag(if_match: Optional[str]) -> int:
    """Parse integer version number from HTTP If-Match header value."""
    if not if_match:
        raise PreconditionFailedError("Missing required 'If-Match' header for optimistic concurrency.")

    clean_etag = if_match.strip()
    # Strip weak prefix W/
    if clean_etag.startswith("W/"):
        clean_etag = clean_etag[2:]
    # Strip surrounding quotes
    clean_etag = clean_etag.strip('"')

    try:
        return int(clean_etag)
    except ValueError:
        raise PreconditionFailedError(f"Malformed If-Match header: '{if_match}'. Expected integer version.")


async def get_public_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an unscoped AsyncSession without tenant RLS context (used for auth / registration)."""
    async with async_session_factory() as session:
        async with session.begin():
            yield session


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_public_session),
) -> User:
    """Validate Bearer JWT and retrieve authenticated User."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid 'Authorization' Bearer header.")

    token = authorization[7:].strip()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedError("JWT token missing 'sub' subject claim.")
        user_id = UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("JWT token has expired.")
    except Exception as ex:
        raise UnauthorizedError(f"Could not validate credentials: {str(ex)}")

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active or user.status != "active":
        raise UnauthorizedError("User is not found, inactive, or suspended.")

    return user


async def get_workspace(
    workspace_id_header: Optional[str] = Header(None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_public_session),
) -> Workspace:
    """Resolve active tenant Workspace and verify user membership and active status."""
    if not workspace_id_header:
        raise ForbiddenError("Header 'X-Workspace-Id' is required to access tenant resources.")

    try:
        workspace_id = UUID(workspace_id_header)
    except ValueError:
        raise ForbiddenError(f"Invalid UUID in X-Workspace-Id header: '{workspace_id_header}'")

    # Check active membership
    stmt = (
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
            Membership.status == "active",
        )
    )
    res = await session.execute(stmt)
    record = res.first()

    if not record:
        raise ForbiddenError("You are not a member of this workspace or membership is not active.")

    _, workspace = record
    return workspace


async def get_db_session(
    workspace: Workspace = Depends(get_workspace),
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an AsyncSession bounded to the tenant workspace via SET LOCAL app.current_workspace_id."""
    async for session in get_tenant_db_session(workspace.id):
        yield session
