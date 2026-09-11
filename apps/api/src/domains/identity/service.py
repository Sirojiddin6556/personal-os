"""Identity and Tenancy domain service."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.domains.identity.models import Membership, User, Workspace
from src.domains.identity.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    WorkspaceCreateRequest,
)
from src.shared.exceptions import ConflictError, NotFoundError, UnauthorizedError
from src.shared.outbox import publish_event


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> TokenResponse:
    """Generate signed JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=int((expire - datetime.now(timezone.utc)).total_seconds()),
    )


class IdentityService:
    """Business logic for User authentication, registration, and Workspace tenancy."""

    async def register(self, session: AsyncSession, data: UserRegisterRequest) -> User:
        # Check if email already exists
        stmt = select(User).where(User.email == data.email)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            raise ConflictError(
                title="Email Already Registered",
                detail=f"User with email '{data.email}' already exists.",
            )

        hashed = hash_password(data.password)
        user = User(
            id=uuid4(),
            email=data.email,
            password_hash=hashed,
            full_name=data.full_name,
            timezone=data.timezone,
            locale=data.locale,
            status="active",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # Automatically create default personal workspace for the user
        slug = f"workspace-{str(user.id)[:8]}"
        workspace = Workspace(
            id=uuid4(),
            name="My Workspace",
            slug=slug,
            owner_id=user.id,
            plan="free",
            plan_tier="free",
            settings={},
        )
        session.add(workspace)
        await session.flush()

        # Add owner membership
        membership = Membership(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
            status="active",
        )
        session.add(membership)

        await publish_event(
            session=session,
            event_type="identity.user_registered.v1",
            aggregate_type="user",
            aggregate_id=user.id,
            workspace_id=workspace.id,
            data={"email": user.email, "full_name": user.full_name},
        )
        await session.commit()
        return user

    async def authenticate(self, session: AsyncSession, data: UserLoginRequest) -> TokenResponse:
        stmt = select(User).where(User.email == data.email)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active or user.status != "active":
            raise UnauthorizedError("Account is inactive or suspended.")

        return create_access_token(user.id)

    async def create_workspace(
        self,
        session: AsyncSession,
        user: User,
        data: WorkspaceCreateRequest,
    ) -> Workspace:
        stmt = select(Workspace).where(Workspace.slug == data.slug)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            raise ConflictError(
                title="Workspace Slug Taken",
                detail=f"Workspace with slug '{data.slug}' already exists.",
            )

        workspace = Workspace(
            id=uuid4(),
            name=data.name,
            slug=data.slug,
            owner_id=user.id,
            plan="free",
            plan_tier=data.plan_tier,
            settings=data.settings,
        )
        session.add(workspace)
        await session.flush()

        membership = Membership(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
            status="active",
        )
        session.add(membership)

        await publish_event(
            session=session,
            event_type="identity.workspace_created.v1",
            aggregate_type="workspace",
            aggregate_id=workspace.id,
            workspace_id=workspace.id,
            data={"name": workspace.name, "slug": workspace.slug},
        )
        await session.commit()
        return workspace

    async def list_user_workspaces(self, session: AsyncSession, user: User) -> List[Workspace]:
        stmt = (
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == user.id, Membership.status == "active")
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())


identity_service = IdentityService()
