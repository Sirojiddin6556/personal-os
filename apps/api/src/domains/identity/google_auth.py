"""Sign in with Google (Google Identity Services ID token).

The web app renders the official Google button; Google returns a signed ID
token (JWT) to the browser, which posts it to ``POST /v1/auth/google``.
We verify signature (Google JWKS), audience (our client id), issuer, expiry and
that the e-mail is verified, then log the user in — creating the account and a
personal workspace on first sign-in.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any, Callable, Dict, Optional

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.domains.identity.models import User
from src.domains.identity.schemas import TokenResponse, UserRegisterRequest
from src.domains.identity.service import create_access_token, identity_service
from src.shared.exceptions import DomainError, UnauthorizedError

logger = logging.getLogger("personal_os.google_auth")

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

_jwks_client: Optional[jwt.PyJWKClient] = None


def _google_signing_key(token: str) -> Any:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client.get_signing_key_from_jwt(token).key


class GoogleSignInNotConfigured(DomainError):
    def __init__(self) -> None:
        super().__init__(
            title="Google Sign-In Not Configured",
            detail="Вход через Google не настроен на сервере (GOOGLE_CLIENT_ID).",
            status=503,
            extensions={"code": "GOOGLE_SIGNIN_NOT_CONFIGURED"},
        )


def verify_google_id_token(
    credential: str,
    client_id: str,
    key_resolver: Callable[[str], Any] = _google_signing_key,
) -> Dict[str, Any]:
    """Return verified claims or raise UnauthorizedError."""
    try:
        key = key_resolver(credential)
        claims = jwt.decode(
            credential,
            key,
            algorithms=["RS256"],
            audience=client_id,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
            leeway=30,
        )
    except Exception as ex:  # bad signature, expired, wrong audience, JWKS unreachable...
        logger.info("Google ID token rejected: %s", type(ex).__name__)
        raise UnauthorizedError("Недействительный токен Google. Попробуйте войти ещё раз.")

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise UnauthorizedError("Токен выдан не Google.")
    email = claims.get("email")
    if not email or claims.get("email_verified") not in (True, "true"):
        raise UnauthorizedError("Email в аккаунте Google не подтверждён.")
    return claims


async def login_with_google(session: AsyncSession, credential: str) -> TokenResponse:
    client_id = (settings.google_client_id or "").strip()
    if not client_id:
        raise GoogleSignInNotConfigured()

    claims = await asyncio.to_thread(verify_google_id_token, credential, client_id)
    email = str(claims["email"]).strip().lower()

    res = await session.execute(select(User).where(User.email.ilike(email)))
    user = res.scalar_one_or_none()

    if user is None:
        # First sign-in: create the account (random unusable password) + personal workspace.
        name = (claims.get("name") or email.split("@")[0]).strip()[:100] or "Пользователь"
        user = await identity_service.register(
            session,
            UserRegisterRequest(
                email=email,
                password=secrets.token_urlsafe(32),
                full_name=name,
                locale=(claims.get("locale") or "ru")[:10],
            ),
        )
        if claims.get("picture"):
            user.avatar_url = claims["picture"]
            await session.commit()
        logger.info("Created user %s via Google Sign-In", user.id)

    if not user.is_active or user.status != "active":
        raise UnauthorizedError("Account is inactive or suspended.")

    return create_access_token(user.id)
