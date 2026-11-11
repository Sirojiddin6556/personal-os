"""One-time sign-up invitations (registration stays closed for everyone else).

The instance owner (the first account on this server) creates a link; whoever
opens it can register once, within INVITE_DAYS, and gets their own workspace.
Only a SHA-256 of the code is stored.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Invite, User

INVITE_DAYS = 7


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


async def instance_owner_id(s: AsyncSession) -> Optional[UUID]:
    res = await s.execute(select(User.id).order_by(User.created_at.asc()).limit(1))
    return res.scalar_one_or_none()


async def is_instance_owner(s: AsyncSession, user_id: UUID) -> bool:
    return await instance_owner_id(s) == user_id


async def create(s: AsyncSession, created_by: UUID, note: str = "", days: int = INVITE_DAYS) -> tuple[Invite, str]:
    """Returns (invite, plain code). Commits."""
    code = secrets.token_urlsafe(12)
    invite = Invite(code_hash=hash_code(code), created_by=created_by, note=note.strip()[:100],
                    expires_at=datetime.now(timezone.utc) + timedelta(days=days))
    s.add(invite)
    await s.commit()
    return invite, code


def usable(invite: Optional[Invite], now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return bool(invite and not invite.revoked and invite.used_at is None and invite.expires_at > now)


async def find(s: AsyncSession, code: str, lock: bool = False) -> Optional[Invite]:
    if not code or len(code) > 64:
        return None
    stmt = select(Invite).where(Invite.code_hash == hash_code(code))
    if lock:
        stmt = stmt.with_for_update()
    invite = (await s.execute(stmt)).scalar_one_or_none()
    return invite if usable(invite) else None


async def active(s: AsyncSession) -> List[Invite]:
    res = await s.execute(
        select(Invite).where(Invite.revoked.is_(False), Invite.used_at.is_(None),
                             Invite.expires_at > datetime.now(timezone.utc))
        .order_by(Invite.created_at)
    )
    return list(res.scalars().all())


async def revoke(s: AsyncSession, invite_id: UUID) -> bool:
    invite = await s.get(Invite, invite_id)
    if invite is None or not usable(invite):
        return False
    invite.revoked = True
    await s.commit()
    return True
