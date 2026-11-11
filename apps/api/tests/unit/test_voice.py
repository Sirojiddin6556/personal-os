"""Voice messages: spoken text normalization and the handler flow (recognizer mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.integrations.telegram import handler, voice


@pytest.mark.parametrize(
    "spoken,expected",
    [
        ("45 тысяч такси.", "45000 такси"),
        ("Сорок пять тысяч на обед!", "45000 на обед"),
        ("ЛИМИТ ПЯТЬ МИЛИОНОВ", "ЛИМИТ 5000000"),
        ("Лимит 5 миллионов.", "Лимит 5000000"),
        ("лимит 3,5 млн", "лимит 3500000"),
        ("лимит полтора миллиона", "лимит 1500000"),
        ("45 000 такси", "45000 такси"),
        ("двести двадцать пять тысяч сто кафе", "225100 кафе"),
        ("Напомни в семь тридцать вечера тренировка", "Напомни в 7 30 вечера тренировка"),
        ("Напомни завтра в 9:00 позвонить Акмалю.", "Напомни завтра в 9:00 позвонить Акмалю"),
        ("Задача – подготовить отчет по кадрам.", "Задача: подготовить отчет по кадрам"),
        ("Купить одну пачку молока", "Купить 1 пачку молока"),
    ],
)
def test_normalize(spoken, expected):
    assert voice.normalize(spoken) == expected


def test_normalized_amount_is_parsed_as_expense():
    import asyncio

    intent = asyncio.run(handler.ai_parse_telegram_message(voice.normalize("45 тысяч такси."), uuid4()))
    assert intent.type == "CREATE_EXPENSE"
    assert intent.data["amount"] == 45000 and intent.data["category"] == "такси"


@pytest.mark.parametrize("text", ["", "  ", "Продолжение следует...", "Субтитры сделал DimaTorzok"])
def test_clean_drops_silence_hallucinations(text):
    assert voice.clean(text) == ""


def test_media_and_limits(monkeypatch):
    assert voice.media_of({"voice": {"file_id": "x"}}) == {"file_id": "x"}
    assert voice.media_of({"video_note": {"file_id": "y"}}) == {"file_id": "y"}
    assert voice.media_of({"text": "hi"}) is None
    monkeypatch.setattr(voice.settings, "voice_max_seconds", 180)
    voice.check_media({"duration": 60})
    with pytest.raises(voice.VoiceError, match="3:20"):
        voice.check_media({"duration": 200})


def _update(**media):
    return {"message": {"message_id": 5, "chat": {"id": 42}, "from": {"id": 42}, **media}}


async def test_voice_message_becomes_a_task(monkeypatch):
    monkeypatch.setattr(voice.settings, "voice_enabled", True)
    session = MagicMock(add=MagicMock(), commit=AsyncMock())
    created = MagicMock(title="позвонить Акмалю")
    with patch.object(handler, "send_message", AsyncMock(return_value={"result": {"message_id": 9}})) as send, \
         patch.object(handler, "edit_message", AsyncMock()) as edit, \
         patch.object(handler, "publish_event", AsyncMock()), \
         patch.object(voice, "download", AsyncMock(return_value=b"ogg")), \
         patch.object(voice.engine, "transcribe", AsyncMock(return_value="Задача: позвонить Акмалю.")), \
         patch.object(handler.task_service, "create", AsyncMock(return_value=created)) as create:
        await handler.handle_telegram_update(_update(voice={"file_id": "f", "duration": 4}),
                                             session=session, workspace_id=uuid4())
    assert send.await_args_list[0].args[1].startswith("🎙 Распознаю")
    assert edit.await_args.args[2] == "🎙 «Задача: позвонить Акмалю.»"
    assert create.await_args.args[2].title == "позвонить Акмалю"
    item = session.add.call_args.args[0]
    assert item.raw_content == "Задача: позвонить Акмалю" and item.status == "processed"


async def test_voice_too_long_is_refused_without_download(monkeypatch):
    monkeypatch.setattr(voice.settings, "voice_enabled", True)
    with patch.object(handler, "send_message", AsyncMock()) as send, \
         patch.object(voice, "download", AsyncMock()) as dl:
        await handler.handle_telegram_update(_update(voice={"file_id": "f", "duration": 900}),
                                             session=MagicMock(), workspace_id=uuid4())
    dl.assert_not_awaited()
    assert "слишком длинное" in send.await_args.args[1]


async def test_silence_is_reported_and_not_saved(monkeypatch):
    monkeypatch.setattr(voice.settings, "voice_enabled", True)
    session = MagicMock(add=MagicMock(), commit=AsyncMock())
    with patch.object(handler, "send_message", AsyncMock(return_value={"result": {"message_id": 9}})), \
         patch.object(handler, "edit_message", AsyncMock()) as edit, \
         patch.object(voice, "download", AsyncMock(return_value=b"ogg")), \
         patch.object(voice.engine, "transcribe", AsyncMock(return_value="")):
        await handler.handle_telegram_update(_update(voice={"file_id": "f", "duration": 2}),
                                             session=session, workspace_id=uuid4())
    assert "Ничего не расслышал" in edit.await_args.args[2]
    session.add.assert_not_called()


@pytest.mark.parametrize(
    "text,title,local",
    [
        ("завтра в 9 утра позвонить Акмалю", "Позвонить Акмалю", "2026-11-12 09:00"),
        ("в 7 вечера тренировка", "Тренировка", "2026-11-11 19:00"),
        ("в 7 30 вечера тренировка", "Тренировка", "2026-11-11 19:30"),
        ("в 5 забрать сына", "Забрать сына", "2026-11-11 17:00"),
        ("в 19:00 позвонить маме", "Позвонить маме", "2026-11-11 19:00"),
        ("в 10 утра врач", "Врач", "2026-11-12 10:00"),
        ("через 2 часа выпить таблетку", "Выпить таблетку", "2026-11-11 17:00"),
        ("через 15 минут проверить духовку", "Проверить духовку", "2026-11-11 15:15"),
        ("через час выйти", "Выйти", "2026-11-11 16:00"),
        ("через полчаса созвон", "Созвон", "2026-11-11 15:30"),
        ("купить хлеб", "Купить хлеб", "2026-11-11 16:00"),
    ],
)
def test_parse_reminder_spoken_times(text, title, local):
    from datetime import datetime

    now = datetime(2026, 11, 11, 15, 0, tzinfo=handler.REMINDER_TZ)
    got_title, at = handler.parse_reminder(text, now)
    assert got_title == title
    assert at.astimezone(handler.REMINDER_TZ).strftime("%Y-%m-%d %H:%M") == local
