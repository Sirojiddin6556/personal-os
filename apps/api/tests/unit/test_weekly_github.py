"""Weekly review (Sunday 20:00) and GitHub issues -> tasks notices."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.domains.finance import limits
from src.integrations.github.scheduler import notice_text
from src.integrations.telegram import daily, weekly

TZ = ZoneInfo("Asia/Tashkent")


def at(d, h, m=0):
    return datetime(2026, 11, d, h, m, tzinfo=TZ)


@pytest.mark.parametrize(
    "now,sent,expected",
    [
        (at(15, 19, 59), {}, False),  # Sunday, too early
        (at(15, 20, 0), {}, True),
        (at(15, 23, 30), {"weekly": "2026-11-08"}, True),
        (at(15, 21, 0), {"weekly": "2026-11-15"}, False),  # sent already
        (at(14, 20, 0), {}, False),  # Saturday
    ],
)
def test_weekly_window(now, sent, expected):
    assert weekly.is_due(now, sent) is expected
    assert ("weekly" in daily.due_digests(now, sent)) is expected


def test_week_bounds_monday_to_monday():
    start, end = weekly.week_bounds(date(2026, 11, 15), TZ)
    assert (start.date(), end.date()) == (date(2026, 11, 9), date(2026, 11, 16))


def test_weekly_text_full():
    w = weekly.WeekData(
        monday=date(2026, 11, 9),
        done=["Отчёт", "Звонок"],
        overdue=["Счёт"],
        spent=150_000_000,
        spent_prev=100_000_000,
        by_category=[("Продукты", 90_000_000), ("Такси", 60_000_000)],
        habits=[("Спорт", 3)],
        next_events=[(datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc), None, False, "Планёрка")],
        next_due=2,
        day=daily.DayData(month_spent=300_000_000, limit=limits.LimitStatus(500_000_000, 300_000_000, date(2026, 11, 15))),
    )
    text = weekly.weekly_text(w, TZ)
    assert text.startswith("📆 Итоги недели · 9 ноября — 15 ноября")
    assert "✅ Сделано задач: 2" in text and "⚠️ Просрочено сейчас: 1" in text
    assert "Потрачено за неделю: 1 500 000 сум (+50% к прошлой: 1 000 000 сум)" in text
    assert "  Продукты — 900 000 сум" in text
    assert "🟩 Месяц: 3 000 000 сум из 5 000 000 сум (60%)" in text
    assert "• Спорт: 3 из 7" in text
    assert "событий 1, задач со сроком 2" in text and "• пн 16.11 09:30 — Планёрка" in text
    kb = weekly.keyboard(w, date(2026, 11, 15))
    assert kb["inline_keyboard"][0][0]["callback_data"] == "dg:carry:20261115"


def test_weekly_text_quiet_week():
    text = weekly.weekly_text(weekly.WeekData(monday=date(2026, 11, 9)), TZ)
    assert "Закрытых задач на этой неделе нет" in text and "Трат за неделю нет" in text
    assert weekly.keyboard(weekly.WeekData(monday=date(2026, 11, 9)), date(2026, 11, 15)) in (
        None, {"inline_keyboard": [daily.app_button()]})


def test_github_notice_text():
    created = [("personal-os", f"[#{i}] Задача {i}") for i in range(9)]
    text = notice_text(created, [("kadr", "[#3] Старый баг")])
    assert text.startswith("🐙 Новые задачи из GitHub: 9")
    assert "• [#0] Задача 0 (personal-os)" in text and "…и ещё 2" in text
    assert "✅ Закрыты на GitHub: 1\n• [#3] Старый баг" in text
    assert notice_text([], []) == ""


def test_task_enum_status_is_kept():
    from src.domains.tasks.models import Task, TaskPriority, TaskStatus

    t = Task(title="x", status=TaskStatus.DONE, priority=TaskPriority.HIGH)
    assert (t.status, t.priority) == ("done", "high")
    t.status = TaskStatus.TODO
    assert t.status == "todo"
