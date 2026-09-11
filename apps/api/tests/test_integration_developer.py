"""Unit and integration test suite for Stage 11: Integration Developer (Google Calendar & Telegram Bot)."""

import hashlib
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import BackgroundTasks
from starlette.requests import Request

from src.config import settings
from src.domains.identity.models import Workspace
from src.integrations.crypto import decrypt_token, encrypt_token
from src.integrations.google_calendar.router import authorize, callback, disconnect, google_webhook
from src.integrations.google_calendar.sync import (
    GoogleSyncTokenExpired,
    create_event,
    create_mapping,
    full_sync,
    gcal_list_events,
    get_credentials,
    get_mapping,
    get_sync_token,
    incremental_sync,
    parse_gcal_datetime,
    save_sync_token,
    soft_delete_event,
    update_event,
    upsert_event,
)
from src.integrations.models import ExternalMapping, Integration, OAuthCredential, SyncState
from src.integrations.telegram.handler import (
    ai_parse_telegram_message,
    confirm_keyboard,
    handle_telegram_update,
    send_message,
)
from src.integrations.telegram.router import deduplicate_telegram_update, telegram_webhook


# =====================================================================
# 1. AES-256-GCM Cryptography Tests
# =====================================================================

def test_aes_gcm_crypto_roundtrip():
    secret_token = "ya29.sample-google-oauth-access-token-987654321"
    enc = encrypt_token(secret_token)

    assert "ciphertext" in enc
    assert "iv" in enc
    assert "tag" in enc
    assert "combined" in enc
    assert len(enc["iv"]) == 12  # 96-bit nonce
    assert len(enc["tag"]) == 16  # 128-bit auth tag

    # Decrypt using combined bytes
    dec_combined = decrypt_token(enc["combined"])
    assert dec_combined == secret_token

    # Decrypt using separated components
    dec_separate = decrypt_token(enc["ciphertext"], iv=enc["iv"], tag=enc["tag"])
    assert dec_separate == secret_token


def test_aes_gcm_credential_object_decryption():
    secret = "refresh-token-xyz-12345"
    enc = encrypt_token(secret)

    cred = OAuthCredential(
        id=uuid4(),
        workspace_id=uuid4(),
        integration_id=uuid4(),
        encrypted_access_token=enc["ciphertext"],
        iv_access=enc["iv"],
        tag_access=enc["tag"],
        key_version=1,
    )

    dec = decrypt_token(cred)
    assert dec == secret


def test_aes_gcm_tamper_detection():
    secret = "secret-data"
    enc = encrypt_token(secret)
    # Corrupt one byte of ciphertext
    tampered = bytearray(enc["combined"])
    tampered[15] ^= 0xFF

    with pytest.raises(Exception):
        decrypt_token(bytes(tampered))


# =====================================================================
# 2. Google Calendar OAuth & PKCE Tests
# =====================================================================

@pytest.mark.asyncio
async def test_google_authorize_url_generation():
    workspace = Workspace(id=uuid4(), name="Test Workspace", slug="test-ws")
    result = await authorize(workspace=workspace)

    assert "auth_url" in result
    url = result["auth_url"]
    assert "accounts.google.com" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "access_type=offline" in url
    assert "state=" in url

    # Parse state JWT
    state_param = url.split("state=")[1].split("&")[0]
    decoded = jwt.decode(state_param, settings.secret_key, algorithms=[settings.jwt_algorithm])
    assert decoded["workspace_id"] == str(workspace.id)
    assert "code_verifier" in decoded


@pytest.mark.asyncio
async def test_google_callback_exchanges_and_encrypts():
    workspace_id = uuid4()
    state_payload = {
        "workspace_id": str(workspace_id),
        "code_verifier": "test-verifier",
        "exp": int(time.time()) + 300,
    }
    state = jwt.encode(state_payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    mock_session = AsyncMock()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    bg_tasks = BackgroundTasks()

    res = await callback(
        code="mock-auth-code",
        state=state,
        background_tasks=bg_tasks,
        session=mock_session,
    )

    assert res == {"status": "connected"}
    assert mock_session.add.call_count >= 1
    assert mock_session.commit.called
    assert len(bg_tasks.tasks) == 1


# =====================================================================
# 3. Google Calendar Sync & Delta Token Tests
# =====================================================================

def test_parse_gcal_datetime():
    dt, is_all_day = parse_gcal_datetime({"dateTime": "2026-09-11T15:30:00Z"})
    assert dt.hour == 15
    assert dt.minute == 30
    assert not is_all_day

    dt_all_day, is_all_day = parse_gcal_datetime({"date": "2026-09-11"})
    assert dt_all_day.day == 11
    assert is_all_day


@pytest.mark.asyncio
async def test_gcal_list_events_mock_mode():
    resp = await gcal_list_events(access_token="mock-token-test")
    assert "items" in resp
    assert "nextSyncToken" in resp
    assert len(resp["items"]) >= 1


@pytest.mark.asyncio
async def test_google_full_and_incremental_sync_lifecycle():
    workspace_id = uuid4()
    integ_id = uuid4()
    enc = encrypt_token("mock-token-full-sync")

    cred = OAuthCredential(
        id=uuid4(),
        workspace_id=workspace_id,
        integration_id=integ_id,
        encrypted_access_token=enc["combined"],
        iv_access=enc["iv"],
        tag_access=enc["tag"],
        key_version=1,
    )

    mock_session = AsyncMock()
    # Mock no existing mapping
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=None),
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
    )

    # 1. Test full sync
    await full_sync(mock_session, workspace_id, credentials=cred)
    assert mock_session.commit.called

    # 2. Test incremental sync
    with patch("src.integrations.google_calendar.sync.get_sync_token", return_value="mock-token-123"):
        with patch("src.integrations.google_calendar.sync.get_credentials", return_value=cred):
            await incremental_sync(mock_session, workspace_id)
            assert mock_session.commit.called


@pytest.mark.asyncio
async def test_google_incremental_sync_410_fallback():
    workspace_id = uuid4()
    cred = OAuthCredential(
        id=uuid4(),
        workspace_id=workspace_id,
        integration_id=uuid4(),
        encrypted_access_token=encrypt_token("mock-test")["combined"],
        iv_access=b"0" * 12,
        tag_access=b"0" * 16,
    )

    mock_session = AsyncMock()

    with patch("src.integrations.google_calendar.sync.get_credentials", return_value=cred):
        with patch("src.integrations.google_calendar.sync.get_sync_token", return_value="expired-token"):
            with patch(
                "src.integrations.google_calendar.sync.gcal_list_events",
                side_effect=GoogleSyncTokenExpired("410 Gone"),
            ):
                with patch("src.integrations.google_calendar.sync.full_sync", new_callable=AsyncMock) as mock_full:
                    await incremental_sync(mock_session, workspace_id)
                    assert mock_full.called


# =====================================================================
# 4. Telegram Webhook & Fast ACK Tests
# =====================================================================

@pytest.mark.asyncio
async def test_telegram_deduplication():
    update_id = f"upd-{uuid4()}"

    # First attempt: should pass
    first_attempt = await deduplicate_telegram_update(update_id)
    assert first_attempt is True

    # Duplicate attempt: should be detected
    second_attempt = await deduplicate_telegram_update(update_id)
    assert second_attempt is False


@pytest.mark.asyncio
async def test_telegram_webhook_fast_ack():
    bg_tasks = BackgroundTasks()

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/telegram",
        "headers": [(b"content-type", b"application/json")],
    }
    raw_body = b'{"update_id": 999123, "message": {"text": "hello", "chat": {"id": 12345}}}'

    async def receive():
        return {"type": "http.request", "body": raw_body, "more_body": False}

    request = Request(scope=scope, receive=receive)

    res = await telegram_webhook(
        request=request,
        background_tasks=bg_tasks,
        bot_token="test-token",
    )

    assert res == {"ok": True}
    assert len(bg_tasks.tasks) == 1


# =====================================================================
# 5. Telegram AI Intent Classification & Handler Tests
# =====================================================================

@pytest.mark.asyncio
async def test_ai_parse_telegram_intents():
    wid = uuid4()

    # Task intent
    t_intent = await ai_parse_telegram_message("Задача: Подготовить квартальный отчет", wid)
    assert t_intent.type == "CREATE_TASK"
    assert t_intent.data["title"] == "Подготовить квартальный отчет"

    # Expense intent with keyword
    e_intent = await ai_parse_telegram_message("Расход: 750 руб обед", wid)
    assert e_intent.type == "CREATE_EXPENSE"
    assert e_intent.data["amount"] == 750.0
    assert "обед" in e_intent.data["category"]

    # Direct expense
    d_intent = await ai_parse_telegram_message("1200 руб такси", wid)
    assert d_intent.type == "CREATE_EXPENSE"
    assert d_intent.data["amount"] == 1200.0
    assert "такси" in d_intent.data["category"]

    # Reminder intent
    r_intent = await ai_parse_telegram_message("Напомни позвонить стоматологу", wid)
    assert r_intent.type == "CREATE_REMINDER"
    assert "стоматологу" in r_intent.data["title"]

    # Unknown
    u_intent = await ai_parse_telegram_message("бла бла бла неясный текст", wid)
    assert u_intent.type == "UNKNOWN"


@pytest.mark.asyncio
async def test_handle_telegram_update_creates_task():
    workspace_id = uuid4()
    mock_session = AsyncMock()

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_id,
        provider="telegram",
        status="connected",
        config={"chat_id": "112233"},
    )
    mock_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[integ]))),
        scalar_one_or_none=MagicMock(return_value=None),
    )

    update = {
        "update_id": 555001,
        "message": {
            "text": "Задача: Написать автотесты для интеграций",
            "chat": {"id": 112233},
        },
    }

    with patch("src.integrations.telegram.handler.send_message", new_callable=AsyncMock) as mock_send:
        await handle_telegram_update(update, session=mock_session)
        assert mock_send.called
        sent_text = mock_send.call_args[0][1]
        assert "✅ Задача создана" in sent_text


@pytest.mark.asyncio
async def test_handle_telegram_update_prompts_expense_confirmation():
    workspace_id = uuid4()
    mock_session = AsyncMock()

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_id,
        provider="telegram",
        status="connected",
        config={"chat_id": "112233"},
    )
    mock_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[integ]))),
        scalar_one_or_none=MagicMock(return_value=None),
    )

    update = {
        "update_id": 555002,
        "message": {
            "text": "Расход: 450 руб кофе",
            "chat": {"id": 112233},
        },
    }

    with patch("src.integrations.telegram.handler.send_message", new_callable=AsyncMock) as mock_send:
        await handle_telegram_update(update, session=mock_session)
        assert mock_send.called
        sent_text = mock_send.call_args[0][1]
        markup = mock_send.call_args[1].get("reply_markup") or mock_send.call_args[0][2]
        assert "Расход 450.0 руб." in sent_text
        assert markup is not None
        assert "inline_keyboard" in markup
