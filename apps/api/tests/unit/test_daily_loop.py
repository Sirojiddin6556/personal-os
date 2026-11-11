"""Daily Telegram loop: digest windows, texts, inbox buttons."""

from datetime import date, datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from src.integrations.telegram import daily

TZ = ZoneInfo("Asia/Tashkent")


def local(h, m=0, d=12):
    return datetime(2026, 11, d, h, m, tzinfo=TZ)


@pytest.mark.parametrize(
    "now,sent,expected",
    [
        (local(7, 59), {}, []),
        (local(8, 0), {}, ["morning"]),
        (local(10, 30), {}, ["morning"]),  # server was down at 08:00: still sent
        (local(11, 1), {}, []),  # too late for a morning brief
        (local(8, 5), {"morning": "2026-11-12"}, []),  # never twice a day
        (local(8, 5), {"morning": "2026-11-11"}, ["morning"]),
        (local(21, 0), {"morning": "2026-11-12"}, ["evening"]),
        (local(23, 50), {"evening": "2026-11-12"}, []),
    ],
)
def test_due_digests(now, sent, expected):
    assert daily.due_digests(now, sent) == expected


def test_money_formats_minor_units():
    assert daily.money(5_050_000) == "50 500 сум"


def test_morning_text_lists_day():
    data = daily.DayData(
        events=[
            (datetime(2026, 11, 12, 4, 30, tzinfo=timezone.utc), datetime(2026, 11, 12, 5, 0, tzinfo=timezone.utc), False, "Планёрка"),
            (datetime(2026, 11, 12, tzinfo=timezone.utc), datetime(2026, 11, 13, tzinfo=timezone.utc), True, "День рождения"),
        ],
        due_today=["Отчёт"],
        overdue=["Счёт"],
        inbox_pending=2,
        spent_minor=5_050_000,
        spent_by_category=[("Такси", 5_050_000)],
        spent_count=1,
    )
    text = daily.morning_text(date(2026, 11, 12), data, TZ)
    assert text.startswith("☀️ Доброе утро! Четверг, 12 ноября")
    assert "• 09:30–10:00 Планёрка" in text  # shown in local time
    assert "• весь день — День рождения" in text
    assert "⚠️ Просрочено (1)" in text and "✅ Задачи на сегодня (1)" in text
    assert "не разобрано: 2" in text
    assert "Вчера потрачено: 50 500 сум" in text


def test_evening_text_empty_day_is_short_and_friendly():
    text = daily.evening_text(date(2026, 11, 12), daily.DayData(), [], TZ)
    assert "Потрачено сегодня: ничего" in text
    assert "Задач со сроком на сегодня не было" in text


def test_long_lists_are_clipped():
    data = daily.DayData(due_today=[f"Задача {i}" for i in range(12)])
    text = daily.morning_text(date(2026, 11, 12), data, TZ)
    assert "…и ещё 5" in text and "Задача 11" not in text


def test_inbox_buttons_fit_telegram_limit():
    kb = daily.capture_keyboard(uuid4())
    datas = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert {d.split(":")[1] for d in datas} == {"t", "r", "n", "d"}
    assert all(len(d.encode()) <= 64 for d in datas)


def test_app_button_only_for_https(monkeypatch):
    monkeypatch.setattr(daily.settings, "telegram_miniapp_url", "http://localhost/tg/")
    assert daily.app_button() == []
    monkeypatch.setattr(daily.settings, "telegram_miniapp_url", "https://x.trycloudflare.com/tg/")
    assert daily.app_button()[0]["web_app"]["url"].startswith("https://")


async def test_event_reminder_dedupe_memory_fallback(monkeypatch):
    seen = daily._Seen()
    monkeypatch.setattr(daily.settings, "redis_url", "redis://127.0.0.1:1/0")  # unreachable -> memory
    assert await seen.first_time("ev1") is True
    assert await seen.first_time("ev1") is False


async def test_slash_commands_are_not_captured_into_inbox():
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.integrations.telegram import handler

    session = MagicMock(add=MagicMock(), commit=AsyncMock())
    with patch.object(handler, "send_message", AsyncMock()) as send, \
         patch.object(handler, "publish_event", AsyncMock()):
        await handler.handle_telegram_update(
            {"message": {"text": "/stats", "chat": {"id": 1}, "from": {"id": 1}}},
            session=session, workspace_id=uuid4(),
        )
    item = session.add.call_args.args[0]
    assert item.status == "discarded"
    assert "Такой команды нет" in send.await_args.args[1]
