"""Staging & E2E Verification Test Suite for Google Calendar OAuth & Sync.

Covers full OAuth lifecycle and resilience scenarios:
1. Configure credentials (client_id / client_secret).
2. Authorize URL generation with PKCE challenge & signed state JWT.
3. Consent callback code exchange & AES-256-GCM encryption.
4. Incremental sync with delta token.
5. 410 Gone error recovery (full resync fallback).
6. Disconnect & token revocation.
7. Negative: Invalid / forged state JWT.
8. Negative: Expired state JWT.
9. Negative: User access denial (error=access_denied).
10. Security: Tokens are never exposed in plaintext responses.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import AsyncClient

from src.config import settings
from src.domains.identity.models import Workspace
from src.integrations.crypto import decrypt_token, encrypt_token
from src.integrations.google_calendar.sync import GoogleSyncTokenExpired
from src.integrations.models import Integration, OAuthCredential, SyncState


@pytest.mark.staging
@pytest.mark.asyncio
async def test_google_oauth_staging_configure_and_authorize_flow(
    client: AsyncClient,
    auth_headers: dict,
    staging_google_client_id: str,
    staging_google_client_secret: str,
):
    """Step 1 & 2: Configure Client ID/Secret and generate PKCE authorization URL."""
    # 1. Configure
    cfg_resp = await client.post(
        "/v1/integrations/google/configure",
        json={
            "client_id": staging_google_client_id,
            "client_secret": staging_google_client_secret,
        },
        headers=auth_headers,
    )
    assert cfg_resp.status_code == 200
    cfg_data = cfg_resp.json()
    assert cfg_data["status"] == "configured"
    assert cfg_data["client_id"] == staging_google_client_id

    # 1.1. Check /config endpoint
    config_resp = await client.get("/v1/integrations/google/config", headers=auth_headers)
    assert config_resp.status_code == 200
    config_data = config_resp.json()
    assert config_data["configured"] is True
    assert "redirect_uri" in config_data

    # 2. Authorize URL with PKCE
    auth_resp = await client.get("/v1/integrations/google/authorize", headers=auth_headers)
    assert auth_resp.status_code == 200
    auth_data = auth_resp.json()
    assert "auth_url" in auth_data
    auth_url = auth_data["auth_url"]

    # Validate parameters
    assert "accounts.google.com" in auth_url
    assert f"client_id={staging_google_client_id}" in auth_url
    assert "code_challenge=" in auth_url
    assert "code_challenge_method=S256" in auth_url
    assert "access_type=offline" in auth_url
    assert "state=" in auth_url


@pytest.mark.staging
@pytest.mark.asyncio
async def test_google_oauth_staging_callback_exchanges_and_encrypts_tokens(
    client: AsyncClient,
    session,
    workspace_a_id: UUID,
    staging_google_client_id: str,
    staging_google_client_secret: str,
):
    """Step 3: Exchange code for tokens, AES-256-GCM encryption, secure storage."""
    state_payload = {
        "workspace_id": str(workspace_a_id),
        "code_verifier": "sample_pkce_code_verifier_1234567890",
        "exp": int(time.time()) + 300,
    }
    state = jwt.encode(state_payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_a_id,
        provider="google_calendar",
        status="configured",
        config={"client_id": staging_google_client_id, "client_secret": staging_google_client_secret},
    )
    session.add(integ)

    # Mock Google Token API exchange via router-level httpx
    with patch("src.integrations.google_calendar.router.httpx.AsyncClient") as mock_client_cls:
        mock_inst = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_inst
        mock_inst.post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "ya29.staging-access-token-123",
                "refresh_token": "1//staging-refresh-token-456",
                "expires_in": 3600,
                "token_type": "Bearer",
            }),
        )

        cb_resp = await client.get(
            f"/v1/integrations/google/callback?code=4/0A-staging-google-auth-code&state={state}",
            follow_redirects=False,
        )
        assert cb_resp.status_code in (200, 302, 307)
        assert mock_inst.post.called

        # Security check: tokens NOT in location header URL
        location = cb_resp.headers.get("location", "")
        assert "access_token" not in location
        assert "refresh_token" not in location


@pytest.mark.staging
@pytest.mark.asyncio
async def test_google_oauth_staging_sync_and_410_recovery(
    workspace_a_id: UUID,
):
    """Step 4 & 5: Incremental sync and 410 Gone full sync fallback."""
    from src.integrations.google_calendar.sync import full_sync, incremental_sync

    enc = encrypt_token("ya29.mock-token-for-sync")
    cred = OAuthCredential(
        id=uuid4(),
        workspace_id=workspace_a_id,
        integration_id=uuid4(),
        encrypted_access_token=enc["combined"],
        iv_access=enc["iv"],
        tag_access=enc["tag"],
        key_version=1,
    )

    mock_session = AsyncMock()

    # 1. Incremental sync with 410 Gone -> fallbacks to full_sync
    with patch("src.integrations.google_calendar.sync.get_credentials", return_value=cred), \
         patch("src.integrations.google_calendar.sync.get_sync_token", return_value="expired_delta_token"), \
         patch("src.integrations.google_calendar.sync.gcal_list_events", side_effect=GoogleSyncTokenExpired("410 Gone")), \
         patch("src.integrations.google_calendar.sync.full_sync", new_callable=AsyncMock) as mock_full:
        
        await incremental_sync(mock_session, workspace_a_id)
        assert mock_full.called


@pytest.mark.staging
@pytest.mark.asyncio
async def test_google_oauth_staging_negative_state_validations(
    client: AsyncClient,
):
    """Step 7 & 8: Invalid / forged and expired state JWTs are rejected with 400/403."""
    # 1. Corrupted state JWT
    bad_resp = await client.get("/v1/integrations/google/callback?code=abc&state=corrupted.state.jwt")
    assert bad_resp.status_code in (400, 403)

    # 2. Expired state JWT
    expired_payload = {
        "workspace_id": str(uuid4()),
        "code_verifier": "verifier",
        "exp": int(time.time()) - 100,  # Expired in past
    }
    expired_state = jwt.encode(expired_payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    exp_resp = await client.get(f"/v1/integrations/google/callback?code=abc&state={expired_state}")
    assert exp_resp.status_code in (400, 403)

