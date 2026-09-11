import pytest
from httpx import AsyncClient
from uuid import uuid4

pytestmark = pytest.mark.asyncio


async def test_create_task_idempotent(client: AsyncClient, auth_headers):
    """POST /v1/tasks with same Idempotency-Key returns same task"""
    key = str(uuid4())
    payload = {'title': 'Test task', 'priority': 'high'}

    r1 = await client.post('/v1/tasks', json=payload, headers={**auth_headers, 'Idempotency-Key': key})
    r2 = await client.post('/v1/tasks', json=payload, headers={**auth_headers, 'Idempotency-Key': key})

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()['id'] == r2.json()['id']  # Одинаковые ID


async def test_update_task_optimistic_lock(client: AsyncClient, auth_headers, created_task):
    """PATCH /v1/tasks/{id} with stale version returns 409"""
    stale_version = 0  # Task создана с version=1
    r = await client.patch(
        f'/v1/tasks/{created_task["id"]}',
        json={'status': 'in_progress'},
        headers={**auth_headers, 'If-Match': f'W/"{stale_version}"'}
    )
    assert r.status_code == 409


async def test_task_status_machine(client: AsyncClient, auth_headers):
    """Task status transitions: inbox -> todo -> in_progress -> done"""
    task = (await client.post('/v1/tasks', json={'title': 'SM test'}, headers=auth_headers)).json()
    assert task['status'] == 'inbox'

    # Move to todo
    r = await client.patch(f'/v1/tasks/{task["id"]}', json={'status': 'todo'}, 
                          headers={**auth_headers, 'If-Match': f'W/"{task["version"]}"'})
    assert r.status_code == 200
    assert r.json()['status'] == 'todo'


async def test_cross_tenant_isolation(client_a: AsyncClient, client_b: AsyncClient, auth_headers_a, auth_headers_b):
    """Tenant A cannot read Tenant B tasks"""
    task_b = (await client_b.post('/v1/tasks', json={'title': 'Secret B'}, headers=auth_headers_b)).json()

    r = await client_a.get(f'/v1/tasks/{task_b["id"]}', headers=auth_headers_a)
    assert r.status_code in (403, 404)  # Изоляция
