"""Tests for Telegram Mini App initData validation and login/link flows."""

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from src.domains.identity import telegram_auth
from src.domains.identity.telegram_auth import (
    InitDataError,
    TelegramNotLinkedError,
    validate_init_data,
)
from src.shared.exceptions import UnauthorizedError

BOT_TOKEN = "123456:TEST-token"
OTHER_TOKEN = "654321:OTHER-token"


def make_init_data(token: str = BOT_TOKEN, user_id: int = 42, auth_date=None, extra=None, tamper=None) -> str:
    fields = {
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "Siroj", "username": "siroj"}, separators=(",", ":")),
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
    }
    if extra:
        fields.update(extra)
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if tamper:
        fields.update(tamper)
    return urlencode(fields)


# ---------------------------------------------------------------- validation
def test_valid_init_data_returns_user():
    data = validate_init_data(make_init_data(), BOT_TOKEN, 3600)
    assert data["user"]["id"] == 42
    assert data["user"]["first_name"] == "Siroj"


def test_signature_field_is_part_of_check_string():
    data = validate_init_data(make_init_data(extra={"signature": "abc"}), BOT_TOKEN, 3600)
    assert data["signature"] == "abc"


@pytest.mark.parametrize(
    "init_data,token",
    [
        (make_init_data(token=OTHER_TOKEN), BOT_TOKEN),  # signed by another bot
        (make_init_data(tamper={"user": json.dumps({"id": 1})}), BOT_TOKEN),  # tampered user
        (make_init_data(tamper={"hash": "0" * 64}), BOT_TOKEN),
        ("user=%7B%7D&auth_date=1", BOT_TOKEN),  # no hash
        ("", BOT_TOKEN),
        (make_init_data(), ""),
    ],
)
def test_invalid_init_data_rejected(init_data, token):
    with pytest.raises(InitDataError):
        validate_init_data(init_data, token, 3600)


def test_expired_init_data_rejected():
    old = int(time.time()) - 7200
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(auth_date=old), BOT_TOKEN, 3600)


def test_future_auth_date_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(auth_date=int(time.time()) + 3600), BOT_TOKEN, 3600)


def test_duplicate_keys_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data() + "&auth_date=1", BOT_TOKEN, 3600)


# ---------------------------------------------------------------- login flow
def _integration(workspace_id, **config):
    return SimpleNamespace(id=uuid4(), workspace_id=workspace_id, config=config, status="connected")


@pytest.fixture
def patched(monkeypatch):
    """Patch DB-touching helpers; return a mutable holder for integrations/users."""
    state = SimpleNamespace(integrations=[], users={})
    monkeypatch.setattr(telegram_auth.settings, "telegram_bot_token", BOT_TOKEN)

    async def fake_integrations(session):
        return state.integrations

    async def fake_user_for(session, integ):
        return state.users.get(integ.workspace_id)

    monkeypatch.setattr(telegram_auth, "_telegram_integrations", fake_integrations)
    monkeypatch.setattr(telegram_auth, "_user_for_integration", fake_user_for)
    return state


async def test_login_linked_user_gets_token(patched):
    ws = uuid4()
    user = SimpleNamespace(id=uuid4(), full_name="Siroj", timezone="Asia/Tashkent")
    patched.integrations = [_integration(ws, tg_user_id=42)]
    patched.users[ws] = user

    out = await telegram_auth.login_with_telegram(None, make_init_data())
    assert out["workspace_id"] == ws
    assert out["user"]["id"] == user.id
    assert out["access_token"]


async def test_login_legacy_chat_id_link(patched):
    ws = uuid4()
    patched.integrations = [_integration(ws, chat_id="42")]
    patched.users[ws] = SimpleNamespace(id=uuid4(), full_name="S", timezone="UTC")
    out = await telegram_auth.login_with_telegram(None, make_init_data())
    assert out["workspace_id"] == ws


async def test_login_unlinked_user_gets_not_linked(patched):
    ws = uuid4()
    # Another person's workspace: must NOT be used as a fallback.
    patched.integrations = [_integration(ws, chat_id="999")]
    patched.users[ws] = SimpleNamespace(id=uuid4(), full_name="Other", timezone="UTC")
    with pytest.raises(TelegramNotLinkedError) as ei:
        await telegram_auth.login_with_telegram(None, make_init_data())
    assert ei.value.status == 404
    assert ei.value.extensions["code"] == "TELEGRAM_NOT_LINKED"


async def test_login_bad_signature_unauthorized(patched):
    with pytest.raises(UnauthorizedError):
        await telegram_auth.login_with_telegram(None, make_init_data(token=OTHER_TOKEN))


# ---------------------------------------------------------------- HTTP wiring
async def test_http_endpoints_return_problem_details(patched):
    from httpx import ASGITransport, AsyncClient

    from src.main import app
    from src.shared.deps import get_public_session

    async def no_db():
        yield None

    app.dependency_overrides[get_public_session] = no_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            bad = await client.post("/v1/auth/telegram", json={"init_data": make_init_data(token=OTHER_TOKEN)})
            assert bad.status_code == 401

            unlinked = await client.post("/v1/auth/telegram", json={"init_data": make_init_data()})
            assert unlinked.status_code == 404
            assert unlinked.json()["code"] == "TELEGRAM_NOT_LINKED"
            assert unlinked.json()["telegram_user"]["id"] == 42

            ws = uuid4()
            patched.integrations = [_integration(ws, tg_user_id=42)]
            patched.users[ws] = SimpleNamespace(id=uuid4(), full_name="Siroj", timezone="UTC")
            ok = await client.post("/v1/auth/telegram", json={"init_data": make_init_data()})
            assert ok.status_code == 200
            body = ok.json()
            assert body["workspace_id"] == str(ws)
            assert body["telegram_user"]["first_name"] == "Siroj"
            assert body["access_token"]
    finally:
        app.dependency_overrides.pop(get_public_session, None)
