"""Telegram Mini App authentication.

The Mini App receives a signed ``initData`` string from Telegram. We verify the
signature with the bot token (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app),
map the Telegram user to a linked Personal OS workspace and issue a regular JWT.

Linking model: the ``telegram`` Integration of a workspace stores
``config.tg_user_id`` (and ``config.user_id`` of the Personal OS user). For
backwards compatibility a ``config.chat_id`` equal to the Telegram user id
(private chat linked with ``/start``) also counts as a link.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.domains.identity.models import Membership, User, Workspace
from src.domains.identity.service import create_access_token, verify_password
from src.integrations.models import Integration
from src.shared.exceptions import DomainError, ForbiddenError, UnauthorizedError

logger = logging.getLogger("personal_os.telegram_auth")


class InitDataError(ValueError):
    """initData is malformed, has a bad signature or is expired."""


class TelegramNotLinkedError(DomainError):
    """Valid Telegram user, but no Personal OS workspace is linked to it."""

    def __init__(self, telegram_user: Dict[str, Any]):
        super().__init__(
            title="Telegram Not Linked",
            detail="This Telegram account is not linked to a Personal OS workspace yet.",
            status=404,
            extensions={
                "code": "TELEGRAM_NOT_LINKED",
                "telegram_user": {
                    "id": telegram_user.get("id"),
                    "first_name": telegram_user.get("first_name"),
                    "username": telegram_user.get("username"),
                },
            },
        )


# ---------------------------------------------------------------------------
# Signature validation (pure, unit-testable)
# ---------------------------------------------------------------------------
def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Validate Telegram WebApp initData and return its parsed fields.

    ``user`` is decoded from JSON. Raises InitDataError on any problem.
    """
    if not init_data or not bot_token:
        raise InitDataError("empty initData or bot token")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as ex:
        raise InitDataError("malformed initData") from ex

    fields: Dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise InitDataError(f"duplicate key '{key}'")
        fields[key] = value

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash")
    # 'signature' is the Ed25519 third-party signature; it IS part of the
    # data-check-string for the HMAC check, so it stays in `fields`.

    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("bad signature")

    try:
        auth_date = int(fields.get("auth_date", ""))
    except ValueError as ex:
        raise InitDataError("missing auth_date") from ex
    current = time.time() if now is None else now
    if auth_date > current + 60 or current - auth_date > max_age_seconds:
        raise InitDataError("initData expired")

    result: Dict[str, Any] = dict(fields)
    try:
        result["user"] = json.loads(fields["user"])
    except (KeyError, ValueError) as ex:
        raise InitDataError("missing user") from ex
    if not isinstance(result["user"], dict) or not isinstance(result["user"].get("id"), int):
        raise InitDataError("invalid user")
    return result


# ---------------------------------------------------------------------------
# Bot / workspace resolution
# ---------------------------------------------------------------------------
@dataclass
class _BotCandidate:
    token: str
    integration: Optional[Integration]  # None => global TELEGRAM_BOT_TOKEN


@dataclass
class VerifiedTelegramUser:
    user: Dict[str, Any]
    bot_integration: Optional[Integration]


async def _telegram_integrations(session: AsyncSession) -> List[Integration]:
    res = await session.execute(
        select(Integration).where(
            Integration.provider == "telegram",
            Integration.status == "connected",
        )
    )
    return list(res.scalars().all())


def _bot_candidates(integrations: List[Integration]) -> List[_BotCandidate]:
    from src.integrations.crypto import crypto_service

    candidates: List[_BotCandidate] = []
    global_token = (settings.telegram_bot_token or "").strip()
    if global_token and not global_token.startswith("mock-"):
        candidates.append(_BotCandidate(global_token, None))

    for integ in integrations:
        enc_hex = (integ.config or {}).get("enc_token")
        if not enc_hex:
            continue
        try:
            token = crypto_service.decrypt_token(bytes.fromhex(enc_hex))
        except Exception as ex:  # corrupted / rotated key
            logger.warning("Cannot decrypt bot token of integration %s: %s", integ.id, ex)
            continue
        candidates.append(_BotCandidate(token, integ))
    return candidates


async def verify_telegram_init_data(session: AsyncSession, init_data: str) -> VerifiedTelegramUser:
    """Find the bot whose token signed this initData and return the Telegram user."""
    integrations = await _telegram_integrations(session)
    for cand in _bot_candidates(integrations):
        try:
            parsed = validate_init_data(
                init_data, cand.token, settings.telegram_init_data_max_age_seconds
            )
        except InitDataError:
            continue
        return VerifiedTelegramUser(user=parsed["user"], bot_integration=cand.integration)
    raise UnauthorizedError("Invalid or expired Telegram initData.")


def _is_linked(integ: Integration, tg_user_id: int) -> bool:
    cfg = integ.config or {}
    return str(cfg.get("tg_user_id")) == str(tg_user_id) or str(cfg.get("chat_id")) == str(tg_user_id)


async def _user_for_integration(session: AsyncSession, integ: Integration) -> Optional[User]:
    user_id = (integ.config or {}).get("user_id")
    if user_id:
        user = await session.get(User, UUID(str(user_id)))
    else:
        ws = await session.get(Workspace, integ.workspace_id)
        user = await session.get(User, ws.owner_id) if ws else None
    if not user or not user.is_active or user.status != "active":
        return None
    # The user must still be an active member of the workspace.
    res = await session.execute(
        select(Membership.id).where(
            Membership.workspace_id == integ.workspace_id,
            Membership.user_id == user.id,
            Membership.status == "active",
        )
    )
    return user if res.first() else None


def _auth_payload(user: User, workspace_id: UUID, tg_user: Dict[str, Any]) -> Dict[str, Any]:
    token = create_access_token(user.id)
    return {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
        "workspace_id": workspace_id,
        "user": {"id": user.id, "full_name": user.full_name, "timezone": user.timezone},
        "telegram_user": {
            "id": tg_user.get("id"),
            "first_name": tg_user.get("first_name"),
            "username": tg_user.get("username"),
        },
    }


async def login_with_telegram(session: AsyncSession, init_data: str) -> Dict[str, Any]:
    verified = await verify_telegram_init_data(session, init_data)
    tg_id = verified.user["id"]

    if verified.bot_integration is not None:
        # A per-workspace bot can only log into its own workspace.
        scope = [verified.bot_integration]
    else:
        scope = await _telegram_integrations(session)

    for integ in scope:
        if _is_linked(integ, tg_id):
            user = await _user_for_integration(session, integ)
            if user:
                return _auth_payload(user, integ.workspace_id, verified.user)
    raise TelegramNotLinkedError(verified.user)


async def link_telegram_account(
    session: AsyncSession, init_data: str, email: str, password: str
) -> Dict[str, Any]:
    """Link the Telegram user to a Personal OS account (email + password) and log in."""
    verified = await verify_telegram_init_data(session, init_data)

    res = await session.execute(select(User).where(User.email.ilike(email.strip().lower())))
    user = res.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active or user.status != "active":
        raise UnauthorizedError("Account is inactive or suspended.")

    integration = verified.bot_integration
    if integration is not None:
        workspace_id = integration.workspace_id
        res = await session.execute(
            select(Membership.id).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user.id,
                Membership.status == "active",
            )
        )
        if not res.first():
            raise ForbiddenError("This bot belongs to a workspace you are not a member of.")
    else:
        res = await session.execute(
            select(Membership.workspace_id)
            .where(Membership.user_id == user.id, Membership.status == "active")
            .order_by(Membership.created_at)
            .limit(1)
        )
        workspace_id = res.scalar_one_or_none()
        if workspace_id is None:
            raise ForbiddenError("User has no active workspace.")
        res = await session.execute(
            select(Integration).where(
                Integration.workspace_id == workspace_id,
                Integration.provider == "telegram",
            )
        )
        integration = res.scalar_one_or_none()
        if integration is None:
            integration = Integration(
                id=uuid4(),
                workspace_id=workspace_id,
                provider="telegram",
                status="connected",
                config={},
            )
            session.add(integration)

    tg_id = verified.user["id"]
    integration.status = "connected"
    integration.config = {
        **(integration.config or {}),
        "tg_user_id": tg_id,
        "user_id": str(user.id),
        # Private chat id == user id: lets the bot handler route messages too.
        "chat_id": str(tg_id),
    }
    await session.commit()
    return _auth_payload(user, workspace_id, verified.user)
