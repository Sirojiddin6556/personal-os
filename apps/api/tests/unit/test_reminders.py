"""Planner reminders: bot time parsing, creation, and Telegram delivery."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.integrations.telegram import reminders
from src.integrations.telegram.handler import parse_reminder

NOW = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)  # 15:00 in Tashkent


@pytest.mark.parametrize(
    "text,title,expected",
    [
        ("позвонить маме в 19:00", "Позвонить маме", datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)),
        ("завтра в 9:30 врач", "Врач", datetime(2026, 11, 11, 4, 30, tzinfo=timezone.utc)),
        ("выпить воды в 9:00", "Выпить воды", datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)),  # passed -> tomorrow
        ("купить хлеб", "Купить хлеб", NOW + timedelta(hours=1)),
        ("послезавтра оплатить", "Оплатить", datetime(2026, 11, 12, 4, 0, tzinfo=timezone.utc)),
    ],
)
def test_parse_reminder(text, title, expected):
    assert parse_reminder(text, NOW) == (title, expected)


async def test_planner_create_reminder_emits_event_without_type_error():
    from src.domains.planner.schemas import PlannerReminderCreate
    from src.domains.planner.service import planner_service

    session = MagicMock(add=MagicMock(), flush=AsyncMock())
    with patch("src.domains.planner.service.publish_event", new_callable=AsyncMock) as pub:
        r = await planner_service.create_reminder(
            session, uuid4(), PlannerReminderCreate(title="Тест", remind_at=NOW)
        )
    assert r.title == "Тест"
    assert "data" in pub.call_args.kwargs and "payload" not in pub.call_args.kwargs


# ---------------------------------------------------------------- delivery
class _Session:
    def __init__(self, due, integrations):
        self.results = [due, integrations]
        self.commits = 0

    async def execute(self, _stmt):
        items = self.results.pop(0)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: items))

    async def commit(self):
        self.commits += 1


def _reminder(ws, minutes_ago=1, title="Позвонить"):
    return SimpleNamespace(id=uuid4(), workspace_id=ws, title=title, remind_at=NOW - timedelta(minutes=minutes_ago), delivered_at=None)


async def test_due_reminder_is_sent_and_marked():
    ws = uuid4()
    r = _reminder(ws)
    integ = SimpleNamespace(id=uuid4(), workspace_id=ws, config={"chat_id": "42"})
    with patch.object(reminders, "send_message", new_callable=AsyncMock) as send:
        sent = await reminders.deliver_due_reminders(_Session([r], [integ]), now=NOW)
    assert sent == 1
    send.assert_awaited_once()
    assert send.call_args.args[0] == "42" and "Позвонить" in send.call_args.args[1]
    assert r.delivered_at == NOW


async def test_reminder_without_linked_chat_is_closed_not_retried():
    r = _reminder(uuid4())
    with patch.object(reminders, "send_message", new_callable=AsyncMock) as send:
        assert await reminders.deliver_due_reminders(_Session([r], []), now=NOW) == 0
    send.assert_not_called()
    assert r.delivered_at == NOW


async def test_stale_reminder_is_not_spammed():
    ws = uuid4()
    r = _reminder(ws, minutes_ago=60 * 24)
    integ = SimpleNamespace(id=uuid4(), workspace_id=ws, config={"chat_id": "42"})
    with patch.object(reminders, "send_message", new_callable=AsyncMock) as send:
        await reminders.deliver_due_reminders(_Session([r], [integ]), now=NOW)
    send.assert_not_called()
    assert r.delivered_at == NOW


async def test_failed_send_is_retried_later():
    ws = uuid4()
    r = _reminder(ws)
    integ = SimpleNamespace(id=uuid4(), workspace_id=ws, config={"chat_id": "42"})
    with patch.object(reminders, "send_message", new_callable=AsyncMock, side_effect=RuntimeError("telegram down")):
        await reminders.deliver_due_reminders(_Session([r], [integ]), now=NOW)
    assert r.delivered_at is None
