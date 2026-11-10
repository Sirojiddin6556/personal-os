"""Telegram bot: chat linking, pairing codes, expense confirmation, per-bot tokens."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.integrations.telegram import handler
from src.integrations.telegram.handler import (
    confirm_keyboard,
    hash_pairing_code,
    new_pairing_code,
    PAIRING_RE,
)

WS = uuid4()


class FakeSession:
    def __init__(self, integrations):
        self.integrations = integrations
        self.commits = 0

    async def execute(self, _stmt):
        items = self.integrations
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: items))

    async def commit(self):
        self.commits += 1


def integ(**config):
    return SimpleNamespace(id=uuid4(), workspace_id=WS, config=config, status="connected")


def msg(text, chat_id=777, from_id=777):
    return {"message": {"text": text, "chat": {"id": chat_id}, "from": {"id": from_id}}}


@pytest.fixture
def sent():
    with patch.object(handler, "send_message", new_callable=AsyncMock) as m:
        yield m


async def test_stranger_is_not_routed_into_owner_workspace(sent):
    session = FakeSession([integ(chat_id="111")])
    with patch.object(handler.task_service, "create", new_callable=AsyncMock) as create:
        await handler.handle_telegram_update(msg("Задача: взлом"), session=session)
    create.assert_not_called()
    assert "не привязан" in sent.call_args[0][1]


def test_pairing_code_format():
    for _ in range(50):
        assert PAIRING_RE.match(new_pairing_code())


async def test_pairing_code_links_chat(sent):
    code = "POS-ABC234"
    user_id = str(uuid4())
    i = integ(pairing_hash=hash_pairing_code(code), pairing_expires=int(time.time()) + 600, pairing_user_id=user_id)
    session = FakeSession([i])
    await handler.handle_telegram_update(msg(f"/start {code}", chat_id=42, from_id=42), session=session)
    assert i.config["chat_id"] == "42" and i.config["tg_user_id"] == 42 and i.config["user_id"] == user_id
    assert "pairing_hash" not in i.config  # one-time
    assert session.commits == 1
    assert "привязан" in sent.call_args[0][1]


async def test_bare_lowercase_code_also_works(sent):
    code = "POS-XYZ789"
    i = integ(pairing_hash=hash_pairing_code(code), pairing_expires=int(time.time()) + 600)
    await handler.handle_telegram_update(msg("pos-xyz789", chat_id=5), session=FakeSession([i]))
    assert i.config["chat_id"] == "5"


async def test_expired_or_wrong_code_rejected(sent):
    code = "POS-ABC234"
    i = integ(pairing_hash=hash_pairing_code(code), pairing_expires=int(time.time()) - 1)
    await handler.handle_telegram_update(msg(code), session=FakeSession([i]))
    await handler.handle_telegram_update(msg("POS-ZZZZZZ"), session=FakeSession([i]))
    assert "chat_id" not in i.config
    assert all("не подошёл" in c[0][1] for c in sent.call_args_list)


async def test_raw_workspace_uuid_no_longer_links(sent):
    i = integ()
    await handler.handle_telegram_update(msg(f"/start {WS}"), session=FakeSession([i]))
    assert "chat_id" not in i.config


async def test_confirm_expense_records_transaction(sent):
    session = FakeSession([integ(chat_id="777")])
    account = SimpleNamespace(name="Наличные")
    with patch.object(handler, "record_expense", new_callable=AsyncMock, return_value=(object(), account)) as rec, \
         patch.object(handler, "answer_callback", new_callable=AsyncMock):
        update = {"callback_query": {"id": "cb1", "data": "confirm_expense:45000.0:такси", "message": {"chat": {"id": 777}}}}
        await handler.handle_telegram_update(update, session=session)
    rec.assert_awaited_once_with(session, WS, 45000.0, "такси")
    assert "Записано" in sent.call_args[0][1] and "Наличные" in sent.call_args[0][1]


async def test_confirm_expense_from_unlinked_chat_does_nothing(sent):
    with patch.object(handler, "record_expense", new_callable=AsyncMock) as rec, \
         patch.object(handler, "answer_callback", new_callable=AsyncMock):
        update = {"callback_query": {"id": "cb", "data": "confirm_expense:1:x", "message": {"chat": {"id": 999}}}}
        await handler.handle_telegram_update(update, session=FakeSession([integ(chat_id="777")]))
    rec.assert_not_called()


def test_callback_data_fits_64_bytes():
    kb = confirm_keyboard({"amount": 1234567.89, "category": "очень длинная категория расходов " * 3})
    assert len(kb["inline_keyboard"][0][0]["callback_data"].encode("utf-8")) <= 64


async def test_replies_use_the_receiving_bots_token():
    calls = []

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            calls.append(url)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True})

    with patch.object(handler.httpx, "AsyncClient", Client), patch.object(handler.settings, "telegram_bot_token", ""):
        await handler.handle_telegram_update(msg("привет"), session=FakeSession([]), bot_token="123:WORKSPACE-BOT")
    assert calls and calls[0].startswith("https://api.telegram.org/bot123:WORKSPACE-BOT/")
