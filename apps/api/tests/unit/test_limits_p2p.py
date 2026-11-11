"""Monthly spending limit and P2P transfer classification."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.domains.finance import limits
from src.integrations.telegram import bank_flow, daily


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("5 млн", 500_000_000),
        ("5млн", 500_000_000),
        ("3,5 млн", 350_000_000),
        ("5000000", 500_000_000),
        ("5 000 000 сум", 500_000_000),
        ("800 тыс", 80_000_000),
        ("800к", 80_000_000),
        ("выкл", 0),
        ("0", 0),
        ("много", None),
        ("5 млн на еду", None),
    ],
)
def test_parse_limit_amount(raw, expected):
    assert limits.parse_limit_amount(raw) == expected


@pytest.mark.parametrize(
    "text,arg",
    [("лимит", ""), ("Лимит 5 млн", "5 млн"), ("лимит на месяц: 3 млн", "3 млн"), ("бюджет 4 млн", "4 млн")],
)
def test_limit_command_regex(text, arg):
    m = daily.LIMIT_RE.match(text)
    assert m and m[1] == arg


def test_limit_regex_ignores_other_words():
    assert daily.LIMIT_RE.match("лимиты по карте узнать") is None
    assert daily.LIMIT_RE.match("купить лимит") is None


def test_limit_status_math():
    lim = limits.LimitStatus(limit_minor=300_000_000, spent_minor=120_000_000, day=date(2026, 11, 11))
    assert lim.percent == 40
    assert lim.left_minor == 180_000_000
    assert lim.days_left == 20  # 11..30 November
    assert lim.per_day_minor == 9_000_000


def test_crossed_thresholds_once():
    assert limits.crossed(79, []) is None
    assert limits.crossed(80, []) == 80
    assert limits.crossed(85, [80]) is None
    assert limits.crossed(120, [80]) == 100
    assert limits.crossed(130, []) == 100  # jumped straight over both: one warning


def test_month_bounds_december():
    from zoneinfo import ZoneInfo

    start, end = limits.month_bounds(date(2026, 12, 15), ZoneInfo("Asia/Tashkent"))
    assert (start.month, end.year, end.month, end.day) == (12, 2027, 1, 1)


def test_limit_lines_with_and_without_limit():
    lim = limits.LimitStatus(500_000_000, 410_000_000, date(2026, 11, 11))
    lines = daily.limit_lines(daily.DayData(month_spent=410_000_000, limit=lim))
    assert lines[0].startswith("🟨 Месяц: 4 100 000 сум из 5 000 000 сум (82%)")
    assert "по 45 000 сум в день" in lines[1]
    over = daily.limit_lines(daily.DayData(limit=limits.LimitStatus(100_000_000, 150_000_000, date(2026, 11, 11))))
    assert over[0].startswith("🟥") and "превышен на 500 000 сум" in over[1]
    none = daily.limit_lines(daily.DayData(month_spent=10_000_000), hint=True)
    assert none == ["📊 За месяц потрачено: 100 000 сум", "  Задать лимит: напишите «лимит 5 млн»"]
    p2p = daily.limit_lines(daily.DayData(p2p_unsorted=2, p2p_unsorted_minor=15_000_000))
    assert p2p == ["🔁 Переводы без пометки: 2 на 150 000 сум — сейчас считаются расходом"]


def test_mark_limit_announced_reset():
    integ = SimpleNamespace(config={"chat_id": "1", "limit_alerts": {"2026-10": [80, 100], "2026-11": [80]}})
    daily.mark_limit_announced(integ, "2026-11", 100)
    assert integ.config["limit_alerts"] == {"2026-11": [80, 100]}
    daily.mark_limit_announced(integ, "2026-11", 50, reset=True)  # limit raised
    assert integ.config["limit_alerts"] == {"2026-11": []}
    assert integ.config["chat_id"] == "1"


def _notice(merchant, kind="expense", options=None):
    return SimpleNamespace(id=uuid4(), merchant=merchant, kind=kind, options=options or [])


def test_p2p_detection():
    assert bank_flow.is_p2p(_notice("CLICK P2P, UZ"))
    assert bank_flow.is_p2p(_notice("PAYME P2P, UZ"))
    assert not bank_flow.is_p2p(_notice("CLICK OPLATA, UZ"))
    assert not bank_flow.is_p2p(_notice("KORZINKA"))
    assert not bank_flow.is_p2p(_notice("CLICK P2P, UZ", options=[f"pair:{uuid4()}"]))


def test_p2p_buttons_fit_and_mark_current():
    n = _notice("CLICK P2P, UZ", options=["p2p:own"])
    assert bank_flow.p2p_mark(n) == "own"
    row = bank_flow.p2p_row(n, "own")
    assert [b["callback_data"].rsplit(":", 1)[1] for b in row] == ["exp", "own", "debt"]
    assert row[1]["text"].startswith("• ")
    assert all(len(b["callback_data"].encode()) <= 64 for b in row)
    income = bank_flow.p2p_row(_notice("PAYME P2P", kind="income"), None)
    assert [b["text"] for b in income] == ["💰 Это доход", "👤 Со своей карты", "🤝 Вернули долг"]


def test_dashboard_default_limit_is_not_set():
    from src.domains.dashboard.schemas import BudgetSummary

    s = BudgetSummary(total_balance_minor=0, today_spent_minor=0, monthly_spent_minor=0, currency="UZS",
                      active_accounts_count=0)
    assert s.monthly_limit_minor == 0
