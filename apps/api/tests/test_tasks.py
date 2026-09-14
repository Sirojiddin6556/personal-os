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
    """PATCH /v1/tasks/{id} with stale version returns RFC 9110 412 Precondition Failed."""
    stale_version = 0  # Task created with version=1
    r = await client.patch(
        f'/v1/tasks/{created_task["id"]}',
        json={'status': 'in_progress'},
        headers={**auth_headers, 'If-Match': f'"{stale_version}"'}
    )
    assert r.status_code == 412
    data = r.json()
    assert data["status"] == 412
    assert data.get("code") == "STALE_VERSION"


async def test_task_etag_and_precondition_lifecycle(client: AsyncClient, auth_headers):
    """Verify complete ETag lifecycle: GET -> '1', PATCH -> '2', stale -> 412, missing -> 428, weak/wildcard -> 400."""
    # 1. Create task
    create_res = await client.post('/v1/tasks', json={'title': 'ETag Lifecycle Task'}, headers=auth_headers)
    assert create_res.status_code == 201
    assert create_res.headers.get("etag") == '"1"'
    task = create_res.json()
    task_id = task['id']

    # 2. GET task returns ETag: "1"
    get_res = await client.get(f'/v1/tasks/{task_id}', headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.headers.get("etag") == '"1"'

    # 3. Missing If-Match -> 428 Precondition Required
    no_etag_res = await client.patch(f'/v1/tasks/{task_id}', json={'title': 'New Title'}, headers=auth_headers)
    assert no_etag_res.status_code == 428
    assert "application/problem+json" in no_etag_res.headers.get("content-type", "")
    assert no_etag_res.json()["code"] == "PRECONDITION_REQUIRED"

    # 4. Weak ETag W/"1" -> 400 Bad Request
    weak_res = await client.patch(
        f'/v1/tasks/{task_id}',
        json={'title': 'Weak Title'},
        headers={**auth_headers, 'If-Match': 'W/"1"'},
    )
    assert weak_res.status_code == 400
    assert weak_res.json()["code"] == "INVALID_ETAG"

    # 5. Wildcard If-Match: * -> 400 Bad Request
    star_res = await client.patch(
        f'/v1/tasks/{task_id}',
        json={'title': 'Star Title'},
        headers={**auth_headers, 'If-Match': '*'},
    )
    assert star_res.status_code == 400
    assert star_res.json()["code"] == "INVALID_ETAG"

    # 6. Valid If-Match: "1" -> 200 OK + ETag: "2"
    patch_res1 = await client.patch(
        f'/v1/tasks/{task_id}',
        json={'status': 'todo'},
        headers={**auth_headers, 'If-Match': '"1"'},
    )
    assert patch_res1.status_code == 200
    assert patch_res1.headers.get("etag") == '"2"'
    assert patch_res1.json()["version"] == 2

    # 7. Stale If-Match: "1" -> 412 Precondition Failed with problem details
    stale_res = await client.patch(
        f'/v1/tasks/{task_id}',
        json={'status': 'in_progress'},
        headers={**auth_headers, 'If-Match': '"1"'},
    )
    assert stale_res.status_code == 412
    assert "application/problem+json" in stale_res.headers.get("content-type", "")
    stale_body = stale_res.json()
    assert stale_body["code"] == "STALE_VERSION"
    assert stale_body["provided_version"] == 1
    assert stale_body["current_version"] == 2

    # 8. Updated If-Match: "2" -> 200 OK + ETag: "3"
    patch_res2 = await client.patch(
        f'/v1/tasks/{task_id}',
        json={'status': 'in_progress'},
        headers={**auth_headers, 'If-Match': '"2"'},
    )
    assert patch_res2.status_code == 200
    assert patch_res2.headers.get("etag") == '"3"'
    assert patch_res2.json()["version"] == 3


async def test_task_status_machine(client: AsyncClient, auth_headers):
    """Task status transitions: inbox -> todo -> in_progress -> done"""
    task = (await client.post('/v1/tasks', json={'title': 'SM test'}, headers=auth_headers)).json()
    assert task['status'] == 'inbox'

    # Move to todo
    r = await client.patch(f'/v1/tasks/{task["id"]}', json={'status': 'todo'}, 
                          headers={**auth_headers, 'If-Match': f'"{task["version"]}"'})
    assert r.status_code == 200
    assert r.json()['status'] == 'todo'


async def test_cross_tenant_isolation(client_a: AsyncClient, client_b: AsyncClient, auth_headers_a, auth_headers_b):
    """Tenant A cannot read Tenant B tasks"""
    task_b = (await client_b.post('/v1/tasks', json={'title': 'Secret B'}, headers=auth_headers_b)).json()

    r = await client_a.get(f'/v1/tasks/{task_b["id"]}', headers=auth_headers_a)
    assert r.status_code in (403, 404)  # Изоляция
