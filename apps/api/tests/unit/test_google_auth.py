"""Tests for Sign in with Google (ID token verification and login flow)."""

import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.domains.identity import google_auth
from src.domains.identity.google_auth import GoogleSignInNotConfigured, verify_google_id_token
from src.shared.exceptions import UnauthorizedError

CLIENT_ID = "1234-test.apps.googleusercontent.com"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def resolver(_token):
    return KEY.public_key()


def make_token(key=KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1098",
        "email": "Siroj@Example.com",
        "email_verified": True,
        "name": "Siroj",
        "picture": "https://lh3.googleusercontent.com/a/x",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


def test_valid_token():
    claims = verify_google_id_token(make_token(), CLIENT_ID, resolver)
    assert claims["email"] == "Siroj@Example.com"


@pytest.mark.parametrize(
    "token",
    [
        make_token(key=OTHER_KEY),  # forged signature
        make_token(aud="someone-else.apps.googleusercontent.com"),
        make_token(iss="https://evil.example.com"),
        make_token(exp=int(time.time()) - 3600),
        make_token(email_verified=False),
        make_token(email=None),
        "not-a-jwt-at-all-xxxxxxxx",
    ],
)
def test_rejected_tokens(token):
    with pytest.raises(UnauthorizedError):
        verify_google_id_token(token, CLIENT_ID, resolver)


# ---------------------------------------------------------------- login flow
class _Session:
    def __init__(self, user=None):
        self.user = user
        self.commits = 0

    async def execute(self, _stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: self.user)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(google_auth.settings, "google_client_id", CLIENT_ID)
    real = google_auth.verify_google_id_token
    monkeypatch.setattr(
        google_auth, "verify_google_id_token", lambda cred, cid: real(cred, cid, resolver)
    )


async def test_not_configured(monkeypatch):
    monkeypatch.setattr(google_auth.settings, "google_client_id", "")
    with pytest.raises(GoogleSignInNotConfigured):
        await google_auth.login_with_google(_Session(), make_token())


async def test_existing_user_logs_in(configured):
    user = SimpleNamespace(id=uuid4(), is_active=True, status="active")
    token = await google_auth.login_with_google(_Session(user), make_token())
    assert jwt.decode(token.access_token, options={"verify_signature": False})["sub"] == str(user.id)


async def test_new_user_is_registered(configured, monkeypatch):
    created = {}

    async def fake_register(session, data):
        created["data"] = data
        return SimpleNamespace(id=uuid4(), is_active=True, status="active", avatar_url=None)

    monkeypatch.setattr(google_auth.identity_service, "register", fake_register)
    session = _Session(None)
    token = await google_auth.login_with_google(session, make_token())
    assert token.access_token
    assert created["data"].email == "siroj@example.com"  # normalized
    assert created["data"].full_name == "Siroj"
    assert len(created["data"].password) >= 32  # random, unusable
    assert session.commits == 1  # avatar saved


async def test_inactive_user_rejected(configured):
    user = SimpleNamespace(id=uuid4(), is_active=False, status="suspended")
    with pytest.raises(UnauthorizedError):
        await google_auth.login_with_google(_Session(user), make_token())
