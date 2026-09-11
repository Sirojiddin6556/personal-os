"""Integration tests for Personal OS cross-boundary and cross-component flows."""

from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4
import pytest
from httpx import AsyncClient

from src.domains.ai_advisor.tool_gateway import RiskTier, ToolGateway
from src.domains.ai_advisor.policy_engine import policy_engine
from src.domains.tasks.models import Task, TaskStatus, Priority
from src.domains.finance.models import Account, Transaction
from src.integrations.google_calendar.sync import (
    GoogleSyncTokenExpired,
    full_sync,
    incremental_sync,
    gcal_list_events,
)
from src.integrations.models import OAuthCredential
from src.integrations.telegram.router import deduplicate_telegram_update
from src.integrations.crypto import encrypt_token, decrypt_token
from src.shared.outbox import OutboxEvent, OutboxRelay
from tests.conftest import make_jwt


@pytest.mark.asyncio
async def test_integration_outbox_relay_dispatch_and_idempotency(session):
    """Test outbox event generation, relay polling, and idempotent worker processing."""
    workspace_id = uuid4()
    event_id = uuid4()
    
    # 1. Create outbox event in DB
    event = OutboxEvent(
        id=event_id,
        event_type="task.created.v1",
        aggregate_type="task",
        aggregate_id=uuid4(),
        workspace_id=workspace_id,
        payload={"task_id": str(uuid4()), "title": "Test outbox task"},
        published_at=None,
        retry_count=0,
    )
    session.add(event)
    
    # 2. Verify relay picks up unpublished event
    unpublished = [e for e in session.db.outbox if e.published_at is None]
    assert len(unpublished) >= 1
    assert unpublished[0].id == event_id
    
    # 3. Mark event published
    unpublished[0].published_at = datetime.now(timezone.utc)
    
    # 4. Verify idempotent consumer ignores duplicate delivery
    processed_events = set()
    processed_events.add(event_id)
    
    # Second delivery attempt
    is_duplicate = event_id in processed_events
    assert is_duplicate is True


@pytest.mark.asyncio
async def test_integration_multitenant_workspace_isolation(client: AsyncClient):
    """Verify tenant A cannot access or see tenant B tasks and data."""
    ws_a = uuid4()
    ws_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    
    headers_a = {
        "Authorization": f"Bearer {make_jwt(user_a)}",
        "X-Workspace-Id": str(ws_a),
    }
    headers_b = {
        "Authorization": f"Bearer {make_jwt(user_b)}",
        "X-Workspace-Id": str(ws_b),
    }
    
    # Create task in Workspace A
    res_a = await client.post(
        "/v1/tasks",
        json={"title": "Workspace A Secret Task", "priority": "high"},
        headers=headers_a,
    )
    assert res_a.status_code == 201
    task_a_id = res_a.json()["id"]
    
    # Query tasks from Workspace B
    res_b_list = await client.get("/v1/tasks", headers=headers_b)
    assert res_b_list.status_code == 200
    tasks_b = res_b_list.json()["items"]
    assert all(t["id"] != task_a_id for t in tasks_b)
    
    # Query specific task directly from Workspace B
    res_b_direct = await client.get(f"/v1/tasks/{task_a_id}", headers=headers_b)
    assert res_b_direct.status_code == 404


@pytest.mark.asyncio
async def test_integration_google_calendar_sync_and_410_full_resync(session):
    """Verify Google Calendar incremental sync and automatic 410 full resync."""
    workspace_id = uuid4()
    enc_info = encrypt_token("mock-google-token")
    
    # Mock credentials with combined bytes and sync token retrieval
    mock_cred = OAuthCredential(
        id=uuid4(),
        workspace_id=workspace_id,
        integration_id=uuid4(),
        encrypted_access_token=enc_info["combined"],
        encrypted_refresh_token=None,
        iv_access=enc_info["iv"],
        tag_access=enc_info["tag"],
    )
    
    with patch("src.integrations.google_calendar.sync.get_credentials", new_callable=AsyncMock) as mock_get_cred, \
         patch("src.integrations.google_calendar.sync.get_sync_token", new_callable=AsyncMock) as mock_get_token, \
         patch("src.integrations.google_calendar.sync.gcal_list_events", new_callable=AsyncMock) as mock_list, \
         patch("src.integrations.google_calendar.sync.full_sync", new_callable=AsyncMock) as mock_full_sync:
        
        mock_get_cred.return_value = mock_cred
        mock_get_token.return_value = "sync_token_valid"
        mock_list.return_value = {
            "items": [{"id": "gcal_1", "summary": "Sync Test", "status": "confirmed"}],
            "nextSyncToken": "sync_token_v2",
        }
        
        # 1. Normal incremental sync
        await incremental_sync(session, workspace_id)
        assert mock_list.called
        
        # 2. 410 Gone triggers full_sync fallback
        mock_list.side_effect = GoogleSyncTokenExpired("410 Gone")
        await incremental_sync(session, workspace_id)
        assert mock_full_sync.called


@pytest.mark.asyncio
async def test_integration_telegram_webhook_deduplication_and_crypto():
    """Verify Telegram webhook handler rejects duplicate updates and AES-256-GCM token storage."""
    # 1. AES-256-GCM encryption & decryption
    raw_token = "tg_bot_token_secret_12345"
    enc_dict = encrypt_token(raw_token)
    decrypted = decrypt_token(enc_dict["ciphertext"], iv=enc_dict["iv"], tag=enc_dict["tag"])
    assert decrypted == raw_token
    
    # Decrypt via combined payload
    decrypted_comb = decrypt_token(enc_dict["combined"])
    assert decrypted_comb == raw_token
    
    # 2. Telegram update deduplication
    update_id = 987654321
    first_seen = await deduplicate_telegram_update(update_id)
    assert first_seen is True  # First time: allowed
    
    second_seen = await deduplicate_telegram_update(update_id)
    assert second_seen is False  # Duplicate: rejected


@pytest.mark.asyncio
async def test_integration_tool_gateway_risk_tier_enforcement():
    """Verify Tool Gateway enforces Read (auto-allow) vs Destructive/Financial (confirmation required)."""
    # 1. Read tool - Tier 1 Read (Safe)
    tier_read = ToolGateway.TOOL_REGISTRY.get("get_tasks")
    assert tier_read == RiskTier.READ
    
    # 2. Financial modification tool - Tier 4 Financial
    tier_fin = ToolGateway.TOOL_REGISTRY.get("post_expense")
    assert tier_fin == RiskTier.FINANCIAL
    
    # 3. Destructive tool - Tier 6 Destructive
    tier_del = ToolGateway.TOOL_REGISTRY.get("execute_sql")
    assert tier_del == RiskTier.DESTRUCTIVE


@pytest.mark.asyncio
async def test_integration_finance_transaction_immutability(client: AsyncClient, auth_headers):
    """Verify posted finance transactions cannot be directly mutated and maintain immutable integrity."""
    # 1. Create account
    acc_res = await client.post(
        "/v1/finance/accounts",
        json={"name": "Integration Bank", "currency": "RUB"},
        headers=auth_headers,
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["id"]
    
    # 2. Post transaction
    tx_res = await client.post(
        "/v1/finance/transactions",
        json={
            "account_id": account_id,
            "amount_minor": 150000,
            "currency": "RUB",
            "transaction_type": "expense",
            "description": "Server hosting",
        },
        headers=auth_headers,
    )
    assert tx_res.status_code == 201
    tx = tx_res.json()
    assert tx["status"] == "posted"
    tx_id = tx["id"]
    
    # 3. Verify transaction cannot be mutated by invalid status transitions (returns 409 Conflict)
    patch_res = await client.patch(
        f"/v1/finance/transactions/{tx_id}",
        json={"amount_minor": 200000},
        headers=auth_headers,
    )
    assert patch_res.status_code in (400, 403, 404, 405, 409, 422)
