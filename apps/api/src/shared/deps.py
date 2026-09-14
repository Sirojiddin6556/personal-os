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
    BadRequestError,
    ForbiddenError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnauthorizedError,
)


def parse_etag(if_match: Optional[str]) -> int:
    """Parse integer version number from HTTP If-Match header value.

    RFC 9110 / RFC 6585 Rules:
    - Missing If-Match -> 428 Precondition Required
    - Wildcard '*', weak ETags (W/...), lists, or non-numeric values -> 400 Bad Request (INVALID_ETAG)
    - Valid numeric string (e.g. '"1"') -> integer version
    """
    if not if_match:
        raise PreconditionRequiredError("Missing required 'If-Match' header for optimistic concurrency.")

    clean_etag = if_match.strip()

    # Reject wildcard, weak tags, and comma-separated multiple ETags
    if clean_etag == "*" or clean_etag.startswith("W/") or clean_etag.startswith("w/") or "," in clean_etag:
        raise BadRequestError(
            detail=f"Invalid If-Match header: '{if_match}'. Weak ETags, wildcards, and multi-values are not supported for optimistic concurrency.",
            code="INVALID_ETAG",
            extensions={"header": "If-Match", "received_value": if_match},
        )

    # Strip surrounding quotes
    unquoted = clean_etag.strip('"')

    if not unquoted.isdigit():
        raise BadRequestError(
            detail=f"Malformed If-Match header: '{if_match}'. Expected quoted integer version (e.g. '\"1\"').",
            code="INVALID_ETAG",
            extensions={"header": "If-Match", "received_value": if_match},
        )

    return int(unquoted)


async def get_public_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an unscoped AsyncSession without tenant RLS context (used for auth / registration)."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_or_create_default_user(session: AsyncSession) -> User:
    """Retrieve the primary user or create a default user in development/single-user setup."""
    stmt = select(User).where(User.is_active == True).limit(1)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        from src.domains.identity.service import hash_password
        user = User(
            email="siroj@personal-os.local",
            password_hash=hash_password("password123"),
            full_name="Siroj",
            status="active",
            is_active=True,
            timezone="UTC",
            locale="ru",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def get_or_create_default_workspace(session: AsyncSession, user: User) -> Workspace:
    """Retrieve the user's primary workspace or create one if none exists."""
    stmt = (
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(
            Membership.user_id == user.id,
            Membership.status == "active",
        )
        .limit(1)
    )
    res = await session.execute(stmt)
    ws = res.scalar_one_or_none()
    if not ws:
        ws = Workspace(
            name="Personal OS",
            slug="personal-os",
            owner_id=user.id,
            plan="pro",
            plan_tier="pro",
            settings={},
        )
        session.add(ws)
        await session.flush()
        membership = Membership(
            user_id=user.id,
            workspace_id=ws.id,
            role="owner",
            status="active",
        )
        session.add(membership)
        await session.commit()
        await session.refresh(ws)
    return ws


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_public_session),
) -> User:
    """Validate Bearer JWT and retrieve authenticated User, falling back to default user in development."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            user_id_str = payload.get("sub")
            if user_id_str:
                user_id = UUID(user_id_str)
                stmt = select(User).where(User.id == user_id)
                res = await session.execute(stmt)
                user = res.scalar_one_or_none()
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # Development fallback
    if settings.environment == "development":
        return await get_or_create_default_user(session)

    raise UnauthorizedError("Missing or invalid 'Authorization' Bearer header.")


async def get_workspace(
    workspace_id_header: Optional[str] = Header(None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_public_session),
) -> Workspace:
    """Resolve active tenant Workspace and verify user membership and active status."""
    if workspace_id_header:
        try:
            workspace_id = UUID(workspace_id_header)
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
            if record:
                _, workspace = record
                return workspace
        except ValueError:
            pass

    # Default to user's first active workspace or auto-provision in development
    return await get_or_create_default_workspace(session, user)


async def get_db_session(
    workspace: Workspace = Depends(get_workspace),
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an AsyncSession bounded to the tenant workspace via SET LOCAL app.current_workspace_id."""
    async for session in get_tenant_db_session(workspace.id):
        yield session
