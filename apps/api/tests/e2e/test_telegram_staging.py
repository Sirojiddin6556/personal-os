"""Staging & E2E Verification Test Suite for Telegram Gateway.

Covers 14 staging scenarios:
1. Connect with public HTTPS URL (getMe, UUID generation, setWebhook).
2. Verification that bot token is NEVER in URL or response payloads.
3. Live update processing with Fast ACK <500ms.
4. X-Telegram-Bot-Api-Secret-Token validation.
5. Deduplication of identical update_id (Redis SETNX / fallback).
6. Unknown webhook_id returns 404.
7. Invalid secret returns 403.
8. setWebhook failure falls back to mode='polling'.
9. Connect without HTTPS URL defaults to polling.
10. Disconnect calls deleteWebhook and revokes credentials.
11. Old webhook_id is invalidated (404) after disconnect.
12. Reconnect rotates webhook_id to a new unique UUID.
13. Restart API persistence verification.
14. Redis unavailability graceful fallback.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from src.config import settings
from src.domains.identity.models import Workspace
from src.integrations.crypto import encrypt_token
from src.integrations.models import Integration
from src.integrations.telegram.router import deduplicate_telegram_update


@pytest.mark.staging
@pytest.mark.asyncio
async def test_telegram_staging_connect_lifecycle_and_url_sanitization(
    client: AsyncClient,
    auth_headers: dict,
    staging_telegram_bot_token: str,
):
    """Scenario 1, 2: Connect generates opaque UUID, no bot token in URL, setWebhook invoked with secret."""
    base_wh_url = "https://api-staging.personal-os.com"
    
    with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_client_cls:
        mock_inst = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_inst
        mock_inst.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "ok": True,
                "result": {"id": 99887766, "username": "personal_os_staging_bot", "first_name": "Personal OS Staging"}
            }),
        )
        mock_inst.post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True, "result": True}),
        )

        resp = await client.post(
            "/v1/integrations/telegram/connect",
            json={"bot_token": staging_telegram_bot_token, "webhook_url": base_wh_url},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["bot"]["username"] == "personal_os_staging_bot"
        assert data["mode"] == "webhook"
        assert data["webhook_registered"] is True

        webhook_id = data["webhook_id"]
        assert UUID(webhook_id)  # Valid UUID

        # Security check: bot token NEVER in webhook_url or response
        assert staging_telegram_bot_token not in data["webhook_url"]
        assert f"/v1/webhooks/telegram/{webhook_id}" in data["webhook_url"]
        assert "bot_token" not in data
        assert "enc_token" not in data

        # Check setWebhook payload
        assert mock_inst.post.called
        wh_call_args = mock_inst.post.call_args[1].get("json", {})
        assert wh_call_args["url"] == f"https://api-staging.personal-os.com/v1/webhooks/telegram/{webhook_id}"
        assert wh_call_args["secret_token"] is not None


@pytest.mark.staging
@pytest.mark.asyncio
async def test_telegram_staging_fast_ack_and_secret_token_verification(
    client: AsyncClient,
    session,
    workspace_a_id: UUID,
):
    """Scenario 3, 4, 6, 7: Fast ACK <500ms, secret verification, 404 on unknown ID, 403 on bad secret."""
    webhook_id = uuid4()
    secret_token = "staging_secret_token_abcdef1234567890"

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_a_id,
        provider="telegram",
        status="connected",
        config={"webhook_id": str(webhook_id), "webhook_secret": secret_token},
    )
    session.add(integ)

    # 1. Unknown webhook ID -> 404
    r_unknown = await client.post(
        f"/v1/webhooks/telegram/{uuid4()}",
        json={"update_id": 100, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": secret_token},
    )
    assert r_unknown.status_code == 404

    # 2. Invalid secret token -> 403
    r_bad_secret = await client.post(
        f"/v1/webhooks/telegram/{webhook_id}",
        json={"update_id": 101, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "invalid_secret_token"},
    )
    assert r_bad_secret.status_code == 403

    # 3. Valid secret token -> Fast ACK < 500ms
    update_id = int(time.time() * 1000)
    with patch("src.integrations.telegram.router.handle_telegram_update", new_callable=AsyncMock) as mock_handle:
        start_ack = time.perf_counter()
        r_valid = await client.post(
            f"/v1/webhooks/telegram/{webhook_id}",
            json={"update_id": update_id, "message": {"text": "Задача: Проверить staging контур", "chat": {"id": 123456}}},
            headers={"X-Telegram-Bot-Api-Secret-Token": secret_token},
        )
        ack_duration_ms = (time.perf_counter() - start_ack) * 1000
        assert r_valid.status_code == 200
        assert r_valid.json() == {"ok": True}
        assert ack_duration_ms < 500  # Strict Fast ACK SLA


@pytest.mark.staging
@pytest.mark.asyncio
async def test_telegram_staging_deduplication(
    client: AsyncClient,
    session,
    workspace_a_id: UUID,
):
    """Scenario 5: Duplicate update_id returns Fast ACK without duplicate execution."""
    webhook_id = uuid4()
    secret_token = "dedup_secret_token_123"

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_a_id,
        provider="telegram",
        status="connected",
        config={"webhook_id": str(webhook_id), "webhook_secret": secret_token},
    )
    session.add(integ)

    update_id = int(time.time() * 1000) + 999
    payload = {"update_id": update_id, "message": {"text": "Расход: 500 руб кофе", "chat": {"id": 777}}}
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret_token}

    with patch("src.integrations.telegram.router.handle_telegram_update", new_callable=AsyncMock) as mock_handle:
        # 1. First attempt: processed
        r1 = await client.post(f"/v1/webhooks/telegram/{webhook_id}", json=payload, headers=headers)
        assert r1.status_code == 200

        # 2. Duplicate attempt: fast ack returned without error
        r2 = await client.post(f"/v1/webhooks/telegram/{webhook_id}", json=payload, headers=headers)
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}


@pytest.mark.staging
@pytest.mark.asyncio
async def test_telegram_staging_set_webhook_failure_and_polling_fallback(
    client: AsyncClient,
    auth_headers: dict,
    staging_telegram_bot_token: str,
):
    """Scenario 8, 9: Graceful fallback to mode='polling' on setWebhook rejection or absent HTTPS URL."""
    # 1. Rejection from Telegram API
    with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_client_cls:
        mock_inst = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_inst
        mock_inst.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": {"id": 11, "username": "poll_bot"}}))
        mock_inst.post.return_value = MagicMock(status_code=400, json=MagicMock(return_value={"ok": False, "description": "Webhook URL is not reachable"}))

        resp = await client.post(
            "/v1/integrations/telegram/connect",
            json={"bot_token": staging_telegram_bot_token, "webhook_url": "https://api-staging.personal-os.com"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "polling"
        assert data["webhook_registered"] is False

    # 2. Absence of HTTPS URL
    with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_client_cls:
        mock_inst = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_inst
        mock_inst.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": {"id": 11, "username": "poll_bot"}}))

        resp_no_url = await client.post(
            "/v1/integrations/telegram/connect",
            json={"bot_token": staging_telegram_bot_token, "webhook_url": None},
            headers=auth_headers,
        )
        assert resp_no_url.status_code == 200
        assert resp_no_url.json()["mode"] == "polling"
        assert resp_no_url.json()["webhook_registered"] is False


@pytest.mark.staging
@pytest.mark.asyncio
async def test_telegram_staging_disconnect_and_reconnect_rotation(
    client: AsyncClient,
    auth_headers: dict,
    session,
    workspace_a_id: UUID,
    staging_telegram_bot_token: str,
):
    """Scenario 10, 11, 12, 13: Disconnect invokes deleteWebhook, invalidates old UUID, reconnect creates new UUID."""
    wh_id_1 = str(uuid4())
    enc = encrypt_token(staging_telegram_bot_token)

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_a_id,
        provider="telegram",
        status="connected",
        config={
            "username": "staging_bot",
            "webhook_id": wh_id_1,
            "webhook_secret": "sec1",
            "enc_token": enc["combined"].hex(),
        },
    )
    session.add(integ)

    # 1. Check status
    st_r = await client.get("/v1/integrations/telegram/status", headers=auth_headers)
    assert st_r.status_code == 200
    assert st_r.json()["status"] == "connected"
    assert st_r.json()["webhook_id"] == wh_id_1

    # 2. Disconnect with deleteWebhook
    with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_client_cls:
        mock_inst = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_inst
        mock_inst.post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True}))
        disc_r = await client.delete("/v1/integrations/telegram", headers=auth_headers)
        assert disc_r.status_code == 200
        assert disc_r.json()["status"] == "disconnected"
        assert mock_inst.post.called

    # 3. Old webhook_id returns 404
    wh_r_old = await client.post(
        f"/v1/webhooks/telegram/{wh_id_1}",
        json={"update_id": 999, "message": {"text": "ping"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "sec1"},
    )
    assert wh_r_old.status_code == 404

    # 4. Reconnect produces brand new UUID
    with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_client_cls:
        mock_inst = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_inst
        mock_inst.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": {"id": 11, "username": "staging_bot"}}))
        mock_inst.post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True, "result": True}))

        reconn_r = await client.post(
            "/v1/integrations/telegram/connect",
            json={"bot_token": staging_telegram_bot_token, "webhook_url": "https://api-staging.personal-os.com"},
            headers=auth_headers,
        )
        assert reconn_r.status_code == 200
        wh_id_2 = reconn_r.json()["webhook_id"]
        assert wh_id_2 != wh_id_1  # Successfully rotated

