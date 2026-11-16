from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.integrations.health import IntegrationState, describe
from src.integrations.telegram.daily import DayData, morning_text

NOW = datetime(2026, 11, 16, 3, 0, tzinfo=timezone.utc)


def st(provider, status="connected", error=None, config=None, synced=NOW):
    return IntegrationState(provider, status, error, config or {}, synced)


def listener(**cfg):
    base = {"sources": ["humo", "uzcard"], "last_ids": {"humo": 1, "uzcard": 2}}
    base.update(cfg)
    return st("telegram_user", config=base)


def test_all_good_is_silent():
    states = [listener(), st("google_calendar"), st("github"), st("telegram", synced=None)]
    assert describe(states, NOW - timedelta(days=1), NOW) == []


def test_bank_bot_that_stopped_being_read_is_reported():
    # The 2026-11-16 incident: Uzcard had been read (last_ids) but dropped out of sources.
    out = describe([listener(sources=["humo"])], NOW, NOW)
    assert out == ["• Бот Uzcard больше не читается — покупки по карте не записываются"]


def test_error_status_and_sync_error_are_reported():
    out = describe([st("telegram_user", status="error", error="Сеанс завершён"), st("github", error="не обновляются задачи из a/b")], None, NOW)
    assert out == ["• Аккаунт Telegram (уведомления банка): Сеанс завершён", "• GitHub: не обновляются задачи из a/b"]


def test_stale_calendar_and_github():
    out = describe([st("google_calendar", synced=NOW - timedelta(hours=5)), st("github", synced=NOW - timedelta(days=3))], None, NOW)
    assert out == ["• Google Календарь: синхронизация была 5 ч назад", "• GitHub: задачи не обновлялись 3 дн."]
    assert describe([st("google_calendar", synced=None)], None, NOW) == ["• Google Календарь: синхронизация была ни разу"]
    # GitHub that never ran yet (fresh connection) is not an alarm.
    assert describe([st("github", synced=None)], None, NOW) == []


def test_quiet_bank_only_when_listening():
    quiet = NOW - timedelta(days=9)
    assert describe([listener()], quiet, NOW) == [
        "• Уведомлений от банка не было 9 дн. — проверьте в боте карты, что пакет уведомлений активен"
    ]
    assert describe([], quiet, NOW) == []
    assert describe([listener()], None, NOW) == []


def test_morning_digest_shows_problems_first():
    data = DayData(problems=["• Бот Uzcard больше не читается — покупки по карте не записываются"])
    text = morning_text(NOW.date(), data, ZoneInfo("Asia/Tashkent"))
    assert text.splitlines()[2] == "⚠️ Требует внимания:"
    assert "Uzcard" in text.splitlines()[3]
    assert "Требует внимания" not in morning_text(NOW.date(), DayData(), ZoneInfo("Asia/Tashkent"))
