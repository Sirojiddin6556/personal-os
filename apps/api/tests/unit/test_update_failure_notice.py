"""A crashing update must not vanish silently: the webhook already acknowledged it to Telegram."""
from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.telegram import handler


@pytest.mark.parametrize("update", [
    {"update_id": 1, "message": {"chat": {"id": 42}, "text": "кофе 20000"}},
    {"update_id": 2, "callback_query": {"id": "c", "data": "x", "message": {"chat": {"id": 42}}}},
])
async def test_failed_update_tells_the_user(update):
    with patch.object(handler, "_handle_update", AsyncMock(side_effect=RuntimeError("boom"))), \
            patch.object(handler, "send_message", AsyncMock()) as send:
        await handler.handle_telegram_update(update, bot_token="1:T")
    send.assert_awaited_once()
    assert send.await_args.args[0] == 42
    assert "Не получилось" in send.await_args.args[1]
    assert handler._current_bot_token.get() is None  # token context still reset


async def test_failure_without_chat_is_only_logged():
    with patch.object(handler, "_handle_update", AsyncMock(side_effect=RuntimeError("boom"))), \
            patch.object(handler, "send_message", AsyncMock()) as send:
        await handler.handle_telegram_update({"update_id": 3})
    send.assert_not_awaited()
