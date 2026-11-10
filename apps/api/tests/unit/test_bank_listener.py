"""Account listener: trust rules, no history import, no duplicates with manual forwards."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.integrations.telegram import bank_flow, bank_listener, user_account
from src.integrations.telegram.bank_listener import WorkspaceListener, trusted, verified_bot

HUMO_ID = 111
NOTICE = "💸 Оплата\n➖ 101.100,00 UZS\n📍 KORZINKA\n💳 HUMOCARD *1234\n🕓 11:39 15.10.2026"


def msg(i, **kw):
    base = dict(
        id=i, out=False, fwd_from=None, sender_id=HUMO_ID, chat_id=HUMO_ID, message=NOTICE,
        date=datetime(2026, 10, 15, 6, 39, tzinfo=timezone.utc),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_only_messages_written_by_the_bank_bot_are_trusted():
    assert trusted(msg(1), HUMO_ID)
    assert not trusted(msg(1, out=True), HUMO_ID)  # written by the user
    assert not trusted(msg(1, fwd_from=object()), HUMO_ID)  # forwarded into the chat
    assert not trusted(msg(1, sender_id=5), HUMO_ID)
    assert not trusted(msg(1, chat_id=5), HUMO_ID)
    assert not trusted(msg(1, message=""), HUMO_ID)


def test_bank_bot_identity():
    assert verified_bot(SimpleNamespace(bot=True, username="HumoCardBot", id=1), "humo")
    assert verified_bot(SimpleNamespace(bot=True, username="CardXabarBot", id=915326936), "uzcard")
    assert not verified_bot(SimpleNamespace(bot=True, username="CardXabarBot", id=7), "uzcard")
    assert not verified_bot(SimpleNamespace(bot=False, username="HumoCardBot", id=1), "humo")
    assert not verified_bot(SimpleNamespace(bot=True, username="HumoCardBot2", id=1), "humo")


def test_account_and_forward_share_the_fingerprint():
    m = msg(1)
    forwarded = {"forward_origin": {"type": "user", "date": int(m.date.timestamp())}}
    assert bank_flow.fingerprint_raw("humo", int(m.date.timestamp()), NOTICE) == bank_flow.fingerprint("humo", forwarded, NOTICE)


@pytest.fixture
def listener():
    lst = WorkspaceListener(uuid4(), uuid4())
    lst.last_ids = {"humo": 10}
    return lst


async def run_process(lst, messages, chat="777"):
    calls = []

    async def fake_ingest(s, ws, chat_id, provider, text, received, fp, quiet=False):
        calls.append((provider, text, quiet, chat_id))

    class _Ctx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    with patch.object(bank_flow, "ingest", side_effect=fake_ingest), \
            patch.object(bank_listener, "_bot_context", AsyncMock(return_value=("123:T", chat))), \
            patch.object(bank_listener, "_save_cfg", AsyncMock()) as save, \
            patch.object(bank_listener, "_tenant", lambda ws: _Ctx()):
        await lst.process("humo", HUMO_ID, messages)
    return calls, save


async def test_old_and_repeated_messages_are_skipped(listener):
    calls, save = await run_process(listener, [msg(9), msg(10), msg(12), msg(11), msg(12)])
    assert [c[0] for c in calls] == ["humo", "humo"]  # 11 and 12, once each, in order
    assert all(c[2] for c in calls)  # quiet: no chatter about balances/duplicates
    assert listener.last_ids["humo"] == 12
    save.assert_awaited()


async def test_untrusted_message_advances_cursor_but_is_not_recorded(listener):
    calls, _ = await run_process(listener, [msg(11, out=True), msg(12, fwd_from=object())])
    assert calls == []
    assert listener.last_ids["humo"] == 12


async def test_no_linked_chat_means_nothing_is_recorded(listener):
    calls, _ = await run_process(listener, [msg(11)], chat=None)
    assert calls == []


def test_phone_and_hash_validation():
    assert user_account.normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert user_account.mask_phone("+998901234567") == "+998…67"
    with pytest.raises(user_account.LoginError):
        user_account.normalize_phone("123")


async def test_bad_api_hash_is_rejected_before_contacting_telegram():
    with pytest.raises(user_account.LoginError):
        await user_account.start_login(None, uuid4(), 12345, "not-a-hash", "+998901234567")


def test_status_never_exposes_secrets():
    integ = SimpleNamespace(
        status="connected",
        sync_error=None,
        config={
            "enc_session": "aa", "enc_api_hash": "bb", "enc_phone": "cc", "api_id": 1,
            "phone_masked": "+998…67", "tg_username": "@me", "sources": ["humo"],
        },
    )
    out = user_account.status_of(integ)
    assert out == {"status": "connected", "phone": "+998…67", "account": "@me", "error": None, "sources": ["humo"]}
