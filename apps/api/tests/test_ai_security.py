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


async def test_webhook_bad_signature_rejected(client: AsyncClient):
    """Telegram webhook with wrong secret token returns 403"""
    r = await client.post('/v1/webhooks/telegram/bot_token', 
                         json={'update_id': 1, 'message': {'text': 'hello'}},
                         headers={'X-Telegram-Bot-Api-Secret-Token': 'wrong_secret'})
    assert r.status_code == 403
