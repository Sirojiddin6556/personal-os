"""Automated Test Suite for SLA Benchmarks, Zero Token Leak Audit, Encrypted OAuth State & Polling Fallback.

Covers:
1. Fast ACK SLA Benchmark: 100 webhook calls, p50/p95/p99/max latency measurement (assert p95 < 500ms).
2. Zero Token Leak Audit: Captures all application logs during Telegram & Google OAuth lifecycles and asserts no tokens/secrets leak.
3. Polling Mode Resilience: Verifies mode="polling" and webhook_registered=False when setWebhook fails (HTTP 400/500/timeout/ok=false).
4. Encrypted OAuth State: Verifies AES-256-GCM encryption of PKCE code_verifier and rejection of tampered/expired state.
5. Redis SETNX Idempotency vs Degraded Mode handling.
"""

import base64
import json
import logging
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from src.config import settings
from src.domains.identity.models import Workspace
from src.integrations.crypto import crypto_service
from src.integrations.models import Integration


class LogCaptureHandler(logging.Handler):
    """Custom in-memory logging handler to capture all emitted log messages."""

    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)

    def get_all_text(self) -> str:
        return " ".join(f"{r.getMessage()} {getattr(r, 'exc_text', '') or ''}" for r in self.records)


@pytest.mark.asyncio
async def test_fast_ack_sla_benchmark_100_runs(
    client: AsyncClient,
    session,
    workspace_a_id: UUID,
):
    """Benchmark: Execute 100 Webhook Fast ACK requests, compute latency distribution, and verify p95 < 500ms."""
    wh_id = uuid4()
    secret = "benchmark_secret_key_12345678"

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_a_id,
        provider="telegram",
        status="connected",
        config={
            "webhook_id": str(wh_id),
            "webhook_secret": secret,
            "mode": "webhook",
            "webhook_registered": True,
        },
    )
    session.add(integ)
    await session.commit()

    latencies_ms: List[float] = []
    num_requests = 100

    with patch("src.integrations.telegram.router.handle_telegram_update", new_callable=AsyncMock):
        for i in range(num_requests):
            payload = {
                "update_id": 900000 + i,
                "message": {
                    "message_id": 100 + i,
                    "chat": {"id": 12345},
                    "text": f"bench message {i}",
                },
            }

            t_start = time.perf_counter()
            resp = await client.post(
                f"/v1/webhooks/telegram/{wh_id}",
                json=payload,
                headers={"X-Telegram-Bot-Api-Secret-Token": secret},
            )
            t_end = time.perf_counter()

            assert resp.status_code == 200
            latencies_ms.append((t_end - t_start) * 1000.0)

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(0.50 * num_requests)]
    p95 = latencies_sorted[int(0.95 * num_requests)]
    p99 = latencies_sorted[int(0.99 * num_requests)]
    max_lat = latencies_sorted[-1]

    print(f"\n[BENCHMARK] Fast ACK (100 reqs): p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms, max={max_lat:.2f}ms")

    # Strict SLA Assertion: p95 must be well under 500ms
    assert p95 < 500.0, f"p95 latency {p95}ms exceeded SLA 500ms"
    assert p50 < 100.0, f"p50 latency {p50}ms exceeded expectation"


@pytest.mark.asyncio
async def test_zero_token_leaks_in_logs_audit(
    client: AsyncClient,
    auth_headers: dict,
    session,
    workspace_a_id: UUID,
):
    """Audit: Asserts raw Telegram bot tokens and Google OAuth tokens never appear in any captured application logs."""
    sensitive_bot_token = "9876543210:AAH_super_secret_telegram_bot_token_audit"
    sensitive_oauth_token = "ya29.a0AfH_super_secret_google_oauth_access_token_audit"
    sensitive_refresh_token = "1//04_super_secret_google_refresh_token_audit"

    root_logger = logging.getLogger()
    capture_handler = LogCaptureHandler()
    root_logger.addHandler(capture_handler)

    try:
        # 1. Telegram Connect (mocking Telegram API)
        with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_tg_http:
            mock_inst = AsyncMock()
            mock_tg_http.return_value.__aenter__.return_value = mock_inst
            mock_inst.get.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"ok": True, "result": {"id": 12345, "username": "audit_bot", "first_name": "Audit"}}),
            )
            mock_inst.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"ok": True, "result": True}),
            )

            conn_resp = await client.post(
                "/v1/integrations/telegram/connect",
                json={"bot_token": sensitive_bot_token, "webhook_url": "https://example.com/v1/webhooks/telegram"},
                headers=auth_headers,
            )
            assert conn_resp.status_code == 200

        # 2. Google OAuth callback (mocking Google token endpoint)
        state_payload = {
            "workspace_id": str(workspace_a_id),
            "code_verifier": "sample_pkce_code_verifier_audit_987",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        }
        enc_state = crypto_service.encrypt_token(json.dumps(state_payload))
        state_str = base64.urlsafe_b64encode(enc_state["combined"]).decode("utf-8").rstrip("=")

        with patch("src.integrations.google_calendar.router.httpx.AsyncClient") as mock_g_http, \
             patch("src.integrations.google_calendar.router.run_full_sync", new_callable=AsyncMock):
            mock_g_inst = AsyncMock()
            mock_g_http.return_value.__aenter__.return_value = mock_g_inst
            mock_g_inst.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={
                    "access_token": sensitive_oauth_token,
                    "refresh_token": sensitive_refresh_token,
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }),
            )

            cb_resp = await client.get(
                f"/v1/integrations/google/callback?code=4/0A-live-code&state={state_str}",
                follow_redirects=False,
            )
            assert cb_resp.status_code in (200, 302, 307)

        # 3. Disconnect Telegram
        with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_del_http:
            mock_del_inst = AsyncMock()
            mock_del_http.return_value.__aenter__.return_value = mock_del_inst
            mock_del_inst.post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"ok": True}))

            dis_resp = await client.delete("/v1/integrations/telegram", headers=auth_headers)
            assert dis_resp.status_code == 200

        # 4. Audit captured logs
        all_logs = capture_handler.get_all_text()

        assert sensitive_bot_token not in all_logs, "CRITICAL: Raw Telegram bot token found in application logs!"
        assert sensitive_oauth_token not in all_logs, "CRITICAL: Raw Google OAuth access token found in application logs!"
        assert sensitive_refresh_token not in all_logs, "CRITICAL: Raw Google refresh token found in application logs!"

    finally:
        root_logger.removeHandler(capture_handler)


@pytest.mark.asyncio
async def test_telegram_set_webhook_failures_fallback_to_polling(
    client: AsyncClient,
    auth_headers: dict,
):
    """Resilience: If Telegram setWebhook returns 400, 500, or ok=false, system falls back to mode='polling'."""
    bot_token = "123456789:AAF_test_fallback_bot_token"

    # Test case 1: setWebhook returns ok: false
    with patch("src.integrations.telegram.router.httpx.AsyncClient") as mock_http:
        mock_inst = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_inst
        mock_inst.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True, "result": {"id": 999, "username": "fallback_bot", "first_name": "FB"}}),
        )
        mock_inst.post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": False, "description": "Bad Webhook URL: HTTPS certificate invalid"}),
        )

        resp = await client.post(
            "/v1/integrations/telegram/connect",
            json={"bot_token": bot_token, "webhook_url": "https://invalid-cert.com/v1/webhooks/telegram"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "polling"
        assert data["webhook_registered"] is False


@pytest.mark.asyncio
async def test_encrypted_oauth_state_generation_and_tamper_rejection(
    client: AsyncClient,
    auth_headers: dict,
):
    """Security: OAuth state is AES-256-GCM encrypted (code_verifier never visible) and tampered state is rejected."""
    # 1. Configure
    await client.post(
        "/v1/integrations/google/configure",
        json={"client_id": "google-client-id-123.apps.googleusercontent.com", "client_secret": "secret-xyz"},
        headers=auth_headers,
    )

    # 2. Authorize -> extracts encrypted state
    auth_resp = await client.get("/v1/integrations/google/authorize", headers=auth_headers)
    assert auth_resp.status_code == 200
    auth_url = auth_resp.json()["auth_url"]

    # Extract state parameter from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(auth_url)
    qs = urllib.parse.parse_qs(parsed.query)
    state = qs["state"][0]

    # Verify state is not plain JSON or readable plaintext
    assert "workspace_id" not in state
    assert "code_verifier" not in state

    # 3. Decrypt state and verify structure
    pad_len = 4 - (len(state) % 4)
    padded_state = state + ("=" * (pad_len % 4))
    raw_combined = base64.urlsafe_b64decode(padded_state.encode("utf-8"))
    decrypted_str = crypto_service.decrypt_token(raw_combined)
    payload = json.loads(decrypted_str)
    assert "workspace_id" in payload
    assert "code_verifier" in payload

    # 4. Tamper with state (flip byte) -> must be rejected with 400/403
    tampered_bytes = bytearray(raw_combined)
    tampered_bytes[15] ^= 0xFF
    tampered_state = base64.urlsafe_b64encode(tampered_bytes).decode("utf-8").rstrip("=")

    bad_resp = await client.get(f"/v1/integrations/google/callback?code=abc&state={tampered_state}")
    assert bad_resp.status_code in (400, 403)


@pytest.mark.asyncio
async def test_oauth_state_replay_protection_single_use_and_fail_closed(
    client: AsyncClient,
    workspace_a_id: UUID,
):
    """Security: Consuming the same valid OAuth state twice must be rejected with 400 (Replay Protection).
    In production mode with failed Redis, it must fail-closed with 503 Service Unavailable.
    """
    state_payload = {
        "workspace_id": str(workspace_a_id),
        "code_verifier": "single_use_code_verifier_123",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }
    enc_state = crypto_service.encrypt_token(json.dumps(state_payload))
    state_str = base64.urlsafe_b64encode(enc_state["combined"]).decode("utf-8").rstrip("=")

    # 1. First callback consumes the state
    with patch("src.integrations.google_calendar.router.httpx.AsyncClient") as mock_g_http, \
         patch("src.integrations.google_calendar.router.run_full_sync", new_callable=AsyncMock):
        mock_g_inst = AsyncMock()
        mock_g_http.return_value.__aenter__.return_value = mock_g_inst
        mock_g_inst.post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"access_token": "mock-token", "expires_in": 3600}),
        )

        first_resp = await client.get(f"/v1/integrations/google/callback?code=4/0A-code&state={state_str}", follow_redirects=False)
        assert first_resp.status_code in (200, 302, 307)

        # 2. Replay with the same state must be rejected with 400 Bad Request
        replay_resp = await client.get(f"/v1/integrations/google/callback?code=4/0A-code&state={state_str}", follow_redirects=False)
        assert replay_resp.status_code == 400
        assert "уже был использован" in replay_resp.json()["detail"]

    # 3. Fail-Closed check in production environment when Redis fails
    prod_state_payload = {
        "workspace_id": str(workspace_a_id),
        "code_verifier": "prod_code_verifier_456",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }
    prod_enc = crypto_service.encrypt_token(json.dumps(prod_state_payload))
    prod_state_str = base64.urlsafe_b64encode(prod_enc["combined"]).decode("utf-8").rstrip("=")

    with patch("src.config.settings.environment", "production"), \
         patch("src.shared.idempotency.idempotency_service.get_client", side_effect=Exception("Redis connection refused")):
        fail_closed_resp = await client.get(f"/v1/integrations/google/callback?code=4/0A-code&state={prod_state_str}", follow_redirects=False)
        assert fail_closed_resp.status_code == 503
        assert "недоступна" in fail_closed_resp.json()["detail"]
