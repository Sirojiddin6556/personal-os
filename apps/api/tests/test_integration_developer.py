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
from src.integrations.crypto import crypto_service, decrypt_token, encrypt_token
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


def create_mock_session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


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
    mock_integ = Integration(
        id=uuid4(),
        workspace_id=workspace.id,
        provider="google_calendar",
        config={"client_id": "test-client-id-123"},
    )
    mock_session = create_mock_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_integ))
    result = await authorize(session=mock_session, workspace=workspace)

    assert "auth_url" in result
    url = result["auth_url"]
    assert "accounts.google.com" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "access_type=offline" in url
    assert "state=" in url

    # Parse encrypted state (AES-256-GCM protected)
    state_param = url.split("state=")[1].split("&")[0]
    import base64, json
    pad_len = 4 - (len(state_param) % 4)
    padded_state = state_param + ("=" * (pad_len % 4))
    raw_combined = base64.urlsafe_b64decode(padded_state.encode("utf-8"))
    decrypted_str = crypto_service.decrypt_token(raw_combined)
    decoded = json.loads(decrypted_str)
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

    mock_session = create_mock_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    bg_tasks = BackgroundTasks()

    res = await callback(
        code="mock-auth-code",
        state=state,
        background_tasks=bg_tasks,
        session=mock_session,
    )

    assert res.status_code in (200, 302, 307)
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

    mock_session = create_mock_session()
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

    mock_session = create_mock_session()

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
# 4. Telegram Webhook, Opaque UUID & Security Tests (12 Test Requirements)
# =====================================================================

@pytest.mark.asyncio
async def test_telegram_deduplication():
    update_id = f"upd-{uuid4()}"
    assert await deduplicate_telegram_update(update_id) is True
    assert await deduplicate_telegram_update(update_id) is False


@pytest.mark.asyncio
async def test_telegram_connect_creates_unique_webhook_id_and_no_token_in_url():
    """Req 1, 2, 3, 4: Connect generates unique UUID, no bot token in URL, passes secret_token to setWebhook."""
    from src.integrations.telegram.router import TelegramConnectRequest, connect_telegram

    workspace = Workspace(id=uuid4(), name="Test WS", slug="test-ws", owner_id=uuid4())
    mock_session = create_mock_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    base_url = "https://api.personal-os.com"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": {"id": 123456, "username": "test_bot", "first_name": "Test"}}))
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": True}))

        req = TelegramConnectRequest(bot_token=bot_token, webhook_url=base_url)
        res = await connect_telegram(req, session=mock_session, workspace=workspace)

        assert res["status"] == "connected"
        webhook_id_1 = res["webhook_id"]
        assert UUID(webhook_id_1)  # 1. Connect creates valid UUID

        # 2. Ensure bot token is NEVER in the registered URL
        assert bot_token not in res["webhook_url"]
        assert f"/v1/webhooks/telegram/{webhook_id_1}" in res["webhook_url"]

        # 3 & 4. setWebhook payload check
        assert mock_post.called
        post_kwargs = mock_post.call_args[1]
        payload = post_kwargs.get("json", {})
        assert payload["url"] == res["webhook_url"]
        assert payload["url"].endswith(f"/v1/webhooks/telegram/{webhook_id_1}")
        assert payload["secret_token"] is not None
        assert len(payload["secret_token"]) > 20


@pytest.mark.asyncio
async def test_telegram_webhook_unknown_id_and_bad_secret_and_fast_ack():
    """Req 5, 6, 7, 8: 404 on unknown ID, 403 on bad secret, Fast ACK on valid secret, deduplication."""
    from src.integrations.telegram.router import telegram_webhook
    from fastapi import HTTPException

    wh_id = uuid4()
    secret_token = "super_secure_secret_token_123"
    integ = Integration(
        id=uuid4(),
        workspace_id=uuid4(),
        provider="telegram",
        status="connected",
        config={"webhook_id": str(wh_id), "webhook_secret": secret_token},
    )

    mock_session = create_mock_session()
    mock_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[integ])))
    )

    bg_tasks = BackgroundTasks()

    # 5. Unknown webhook_id -> 404
    req_unknown = Request(scope={"type": "http", "method": "POST", "path": f"/webhooks/telegram/{uuid4()}", "headers": []})
    with pytest.raises(HTTPException) as exc_404:
        await telegram_webhook(webhook_id=str(uuid4()), request=req_unknown, background_tasks=bg_tasks, session=mock_session)
    assert exc_404.value.status_code == 404

    # 6. Wrong secret -> 403
    async def wrong_sec_receive():
        return {"type": "http.request", "body": b'{"update_id": 1001, "message": {"text": "hi"}}', "more_body": False}
    req_bad = Request(
        scope={"type": "http", "method": "POST", "path": f"/webhooks/telegram/{wh_id}", "headers": [(b"x-telegram-bot-api-secret-token", b"wrong_token")]},
        receive=wrong_sec_receive,
    )
    with pytest.raises(HTTPException) as exc_403:
        await telegram_webhook(webhook_id=str(wh_id), request=req_bad, background_tasks=bg_tasks, session=mock_session)
    assert exc_403.value.status_code == 403

    # 7. Correct secret -> Fast ACK 200 {"ok": True}
    update_id = int(time.time() * 1000)
    async def ok_receive():
        return {"type": "http.request", "body": f'{{"update_id": {update_id}, "message": {{"text": "hi"}}}}'.encode(), "more_body": False}
    req_ok = Request(
        scope={"type": "http", "method": "POST", "path": f"/webhooks/telegram/{wh_id}", "headers": [(b"x-telegram-bot-api-secret-token", secret_token.encode())]},
        receive=ok_receive,
    )
    res = await telegram_webhook(webhook_id=str(wh_id), request=req_ok, background_tasks=bg_tasks, session=mock_session)
    assert res == {"ok": True}
    assert len(bg_tasks.tasks) == 1

    # 8. Duplicate update_id -> Fast ACK without scheduling new background task
    bg_tasks_2 = BackgroundTasks()
    res_dup = await telegram_webhook(webhook_id=str(wh_id), request=req_ok, background_tasks=bg_tasks_2, session=mock_session)
    assert res_dup == {"ok": True}
    assert len(bg_tasks_2.tasks) == 0


@pytest.mark.asyncio
async def test_telegram_disconnect_and_reconnect_lifecycle():
    """Req 9, 10, 11: deleteWebhook called, old webhook invalidated, reconnect creates new UUID."""
    from src.integrations.telegram.router import (
        TelegramConnectRequest,
        connect_telegram,
        disconnect_telegram,
        get_telegram_status,
        telegram_webhook,
    )
    from fastapi import HTTPException

    workspace = Workspace(id=uuid4(), name="Test WS", slug="test-ws", owner_id=uuid4())
    bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    enc = encrypt_token(bot_token)
    wh_id_1 = str(uuid4())

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace.id,
        provider="telegram",
        status="connected",
        config={
            "username": "test_bot",
            "first_name": "Test",
            "webhook_id": wh_id_1,
            "webhook_secret": "sec1",
            "enc_token": enc["combined"].hex(),
        },
    )

    mock_session = create_mock_session()
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=integ),
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[integ]))),
    )

    # Status check
    status_res = await get_telegram_status(session=mock_session, workspace=workspace)
    assert status_res["status"] == "connected"
    assert status_res["webhook_id"] == wh_id_1

    # 9. Disconnect calls deleteWebhook
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_delete_post:
        mock_delete_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True}))
        disc_res = await disconnect_telegram(session=mock_session, workspace=workspace)
        assert disc_res["status"] == "disconnected"
        assert integ.status == "disconnected"
        assert mock_delete_post.called
        assert "deleteWebhook" in mock_delete_post.call_args[0][0]

    # 10. After disconnect, old webhook_id returns 404
    mock_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    )
    req_scope = Request(scope={"type": "http", "method": "POST", "path": f"/webhooks/telegram/{wh_id_1}", "headers": []})
    with pytest.raises(HTTPException) as exc_disc:
        await telegram_webhook(webhook_id=wh_id_1, request=req_scope, background_tasks=BackgroundTasks(), session=mock_session)
    assert exc_disc.value.status_code == 404

    # 11. Reconnect creates NEW webhook_id
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=integ))
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": {"id": 123456, "username": "test_bot", "first_name": "Test"}}))
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": True}))

        req = TelegramConnectRequest(bot_token=bot_token, webhook_url="https://api.personal-os.com")
        reconnect_res = await connect_telegram(req, session=mock_session, workspace=workspace)
        assert reconnect_res["status"] == "connected"
        wh_id_2 = reconnect_res["webhook_id"]
        assert wh_id_2 != wh_id_1  # Brand new unique UUID


@pytest.mark.asyncio
async def test_telegram_set_webhook_failure_falls_back_to_polling():
    """Req 12: setWebhook error gracefully falls back to mode='polling' and webhook_registered=False."""
    from src.integrations.telegram.router import TelegramConnectRequest, connect_telegram

    workspace = Workspace(id=uuid4(), name="Test WS", slug="test-ws", owner_id=uuid4())
    mock_session = create_mock_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": {"id": 123456, "username": "test_bot", "first_name": "Test"}}))
        # setWebhook returns error
        mock_post.return_value = MagicMock(status_code=400, json=MagicMock(return_value={"ok": False, "description": "Bad Request: HTTPS required"}))

        req = TelegramConnectRequest(bot_token=bot_token, webhook_url="https://api.personal-os.com")
        res = await connect_telegram(req, session=mock_session, workspace=workspace)

        assert res["status"] == "connected"
        assert res["mode"] == "polling"
        assert res["webhook_registered"] is False


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
    mock_session = create_mock_session()

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
    mock_session = create_mock_session()

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


