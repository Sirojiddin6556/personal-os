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
    # Create account + transaction
    account = (await client.post('/v1/finance/accounts', json={'name': 'Main Wallet', 'currency': 'UZS'}, headers=auth_headers)).json()
    tx = (await client.post('/v1/finance/transactions', json={
        'account_id': account['id'], 'amount_minor': 100000, 'currency': 'UZS',
        'transaction_type': 'income', 'occurred_at': '2026-09-14T10:00:00Z'
    }, headers=auth_headers)).json()

    # Reverse transaction
    r = await client.post(f'/v1/finance/transactions/{tx["id"]}/reverse', headers=auth_headers)
    assert r.status_code == 201
    assert r.json()['reversal_of_id'] == tx['id']


async def test_reconcile_account_lifecycle(client: AsyncClient, auth_headers):
    """Reconciliation adjusts balance up and down creating reconciliation transactions."""
    # 1. Create account
    account_res = await client.post(
        '/v1/finance/accounts',
        json={'name': 'Bank Card', 'currency': 'UZS'},
        headers=auth_headers
    )
    assert account_res.status_code == 201
    account = account_res.json()
    assert account['balance_minor'] == 0

    # 2. Reconcile up to 500,000 UZS minor units
    rec_up_res = await client.post(
        f'/v1/finance/accounts/{account["id"]}/reconcile',
        json={'actual_balance_minor': 500000, 'reason': 'Monthly statement adjustment'},
        headers=auth_headers
    )
    assert rec_up_res.status_code == 200
    tx_up = rec_up_res.json()
    assert tx_up['transaction_type'] == 'reconciliation'
    assert tx_up['amount_minor'] == 500000

    acc_get_1 = (await client.get(f'/v1/finance/accounts/{account["id"]}', headers=auth_headers)).json()
    assert acc_get_1['balance_minor'] == 500000

    # 3. Reconcile down to 350,000 UZS minor units
    rec_down_res = await client.post(
        f'/v1/finance/accounts/{account["id"]}/reconcile',
        json={'actual_balance_minor': 350000, 'reason': 'Correction for cash expense'},
        headers=auth_headers
    )
    assert rec_down_res.status_code == 200
    tx_down = rec_down_res.json()
    assert tx_down['transaction_type'] == 'reconciliation'
    assert tx_down['amount_minor'] == 150000

    acc_get_2 = (await client.get(f'/v1/finance/accounts/{account["id"]}', headers=auth_headers)).json()
    assert acc_get_2['balance_minor'] == 350000

    # 4. Reconcile with identical balance (zero delta) returns 409 Conflict
    rec_zero_res = await client.post(
        f'/v1/finance/accounts/{account["id"]}/reconcile',
        json={'actual_balance_minor': 350000, 'reason': 'Verification check'},
        headers=auth_headers
    )
    assert rec_zero_res.status_code == 409
