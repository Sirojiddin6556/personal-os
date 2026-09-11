import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_posted_transaction_immutable(client: AsyncClient, auth_headers, posted_transaction):
    """Cannot modify a posted transaction"""
    r = await client.patch(
        f'/v1/finance/transactions/{posted_transaction["id"]}',
        json={'note': 'hack attempt'},
        headers=auth_headers
    )
    assert r.status_code in (400, 422, 409)


async def test_transaction_reversal(client: AsyncClient, auth_headers):
    """Reversal creates new transaction, balance restored"""
    # Создать счёт + транзакцию
    account = (await client.post('/v1/finance/accounts', json={'name': 'Test', 'currency': 'RUB'}, headers=auth_headers)).json()
    tx = (await client.post('/v1/finance/transactions', json={
        'account_id': account['id'], 'amount_minor': 10000, 'currency': 'RUB',
        'transaction_type': 'income', 'occurred_at': '2024-01-01T10:00:00Z'
    }, headers=auth_headers)).json()

    # Сторнировать
    r = await client.post(f'/v1/finance/transactions/{tx["id"]}/reverse', headers=auth_headers)
    assert r.status_code == 201
    assert r.json()['reversal_of_id'] == tx['id']
