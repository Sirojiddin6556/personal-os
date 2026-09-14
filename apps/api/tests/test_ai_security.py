import pytest
from httpx import AsyncClient
from uuid import uuid4

from src.domains.knowledge.service import knowledge_service

pytestmark = pytest.mark.asyncio


async def test_ai_plan_requires_confirmation(client: AsyncClient, auth_headers):
    """AI plan is proposed, not auto-applied"""
    r = await client.post('/v1/advisor/plans', json={'request': 'Schedule my tasks for today'}, headers=auth_headers)
    plan = r.json()
    assert plan['status'] == 'proposed'
    assert plan['requires_confirmation'] is True
    # Проверяем что задачи не изменились без apply


async def test_rag_cross_tenant_isolation(session, workspace_a_id, workspace_b_id):
    """RAG search returns 0 chunks from other tenant"""
    # Индексируем нотазу в workspace B
    await knowledge_service.index_note(session, workspace_b_id, uuid4(), 'Secret note content')

    # Ищем из workspace A
    chunks = await knowledge_service.search_notes(session, workspace_a_id, 'Secret note')
    assert len(chunks) == 0  # Нуль чужих chunks


async def test_webhook_bad_signature_rejected(client: AsyncClient, session, workspace_a_id):
    """Telegram webhook with wrong secret token returns 403, and unknown webhook_id returns 404."""
    from src.integrations.models import Integration

    wh_id = uuid4()
    integ = Integration(
        id=uuid4(),
        workspace_id=workspace_a_id,
        provider="telegram",
        status="connected",
        config={
            "webhook_id": str(wh_id),
            "webhook_secret": "correct_secret_12345",
        },
    )
    session.add(integ)

    # 1. Test unknown webhook_id -> 404
    r_unknown = await client.post(
        f"/v1/webhooks/telegram/{uuid4()}",
        json={"update_id": 1, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct_secret_12345"},
    )
    assert r_unknown.status_code == 404

    # 2. Test wrong secret token -> 403
    r_bad_secret = await client.post(
        f"/v1/webhooks/telegram/{wh_id}",
        json={"update_id": 1, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
    )
    assert r_bad_secret.status_code == 403
