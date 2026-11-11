"""Voice messages in Telegram -> text, recognized on this server (no cloud, no API keys).

faster-whisper (CTranslate2, int8 on CPU). The model is downloaded once into
``settings.voice_model_dir`` (a separate volume, not part of the daily backup) and
loaded on the first voice message; it is unloaded again after a quiet period so the
shared server gets the memory back. One recognition at a time.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any, Optional

import httpx

from src.config import settings

logger = logging.getLogger("personal_os.voice")

# Whisper tends to "hear" these on silence; such a result is treated as empty.
_HALLUCINATIONS = (
    "продолжение следует",
    "субтитры сделал",
    "субтитры создавал",
    "редактор субтитров",
    "спасибо за просмотр",
)
# Words of the bot's own vocabulary: steers recognition towards them.
PROMPT = "Задача, напомни, лимит, такси, сум, тысяч, миллион, завтра в 9:00."


class VoiceError(Exception):
    """Message for the user."""


SAMPLE_RATE = 16000


def decode(audio: bytes) -> Any:
    """Any container/codec PyAV reads (Telegram OGG/Opus, MP3, M4A, WAV) -> 16 kHz mono float32.

    Done here rather than by faster-whisper: its decoder passes an option newer PyAV removed.
    """
    import av
    import numpy as np

    chunks = []
    with av.open(io.BytesIO(audio), mode="r") as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        raise VoiceError("В сообщении нет звука.")
    return np.concatenate(chunks).astype(np.float32) / 32768.0


class _Engine:
    def __init__(self) -> None:
        self.model: Any = None
        self.last_used = 0.0
        self.lock = asyncio.Lock()
        self._reaper: Optional[asyncio.Task] = None

    def _load(self) -> Any:
        from faster_whisper import WhisperModel

        started = time.monotonic()
        model = WhisperModel(
            settings.voice_model,
            device="cpu",
            compute_type="int8",
            cpu_threads=settings.voice_cpu_threads,
            download_root=settings.voice_model_dir,
        )
        logger.info("Voice model %s loaded in %.1fs", settings.voice_model, time.monotonic() - started)
        return model

    def _run(self, audio: bytes) -> str:
        segments, _info = self.model.transcribe(
            decode(audio),
            language="ru",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=PROMPT,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def transcribe(self, audio: bytes) -> str:
        async with self.lock:
            if self.model is None:
                self.model = await asyncio.to_thread(self._load)
                self._start_reaper()
            started = time.monotonic()
            text = await asyncio.to_thread(self._run, audio)
            self.last_used = time.monotonic()
            logger.info("Voice recognized in %.1fs (%d chars)", self.last_used - started, len(text))
            return clean(text)

    def _start_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap())

    async def _reap(self) -> None:
        while self.model is not None:
            await asyncio.sleep(60)
            if time.monotonic() - self.last_used > settings.voice_idle_unload_seconds and not self.lock.locked():
                self.model = None
                logger.info("Voice model unloaded after idle period")


engine = _Engine()


def clean(text: str) -> str:
    text = " ".join(text.split())
    low = text.lower().strip(" .!…")
    if not low or any(low.startswith(h) for h in _HALLUCINATIONS):
        return ""
    return text


_UNITS = {
    "ноль": 0, "один": 1, "одна": 1, "одну": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5,
    "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12,
    "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19, "полтора": 1.5, "полторы": 1.5,
}
_TENS = {"двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
         "восемьдесят": 80, "девяносто": 90}
_HUNDREDS = {"сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500, "шестьсот": 600,
             "семьсот": 700, "восемьсот": 800, "девятьсот": 900}


def _scale(word: str) -> int:
    if word.startswith(("тысяч", "тыщ")) or word in ("тыс", "тыс."):
        return 1000
    if word.startswith(("миллион", "милион")) or word in ("млн", "млн."):
        return 1_000_000
    return 0


def words_to_digits(text: str) -> str:
    """'сорок пять тысяч такси' -> '45000 такси', 'в семь тридцать' -> 'в 7 30',
    'лимит пять милионов' -> 'лимит 5000000' (Whisper often spells numbers out)."""
    out: list = []
    total = group = 0.0
    rank = 9  # 3 hundreds > 2 tens > 1 units: inside a number each word must be smaller
    active = False

    def flush() -> None:
        nonlocal total, group, rank, active
        if active:
            value = total + group
            out.append(str(int(value)) if value == int(value) else str(value).replace(".", ","))
        total = group = 0.0
        rank, active = 9, False

    for raw in text.split():
        word = raw.lower().strip(",.!?;:")
        tail = raw[len(raw.rstrip(",.!?;:")):]
        kind = 3 if word in _HUNDREDS else 2 if word in _TENS else 1 if word in _UNITS else 0
        scale = _scale(word)
        if kind:
            if kind >= rank or (kind == 1 and rank == 1):
                flush()
            group += (_HUNDREDS.get(word) or _TENS.get(word) or _UNITS[word])
            rank, active = kind, True
        elif scale and (active or (out and _is_number(out[-1]))):
            if not active:  # "45 тысяч": the number was already a digit token
                group, active = float(out.pop().replace(",", ".")), True
            total += (group or 1) * scale
            group, rank = 0.0, 9
        else:
            flush()
            out.append(raw)
            continue
        if tail:
            flush()
            out[-1] += tail
    flush()
    return " ".join(out)


def _is_number(token: str) -> bool:
    import re

    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?", token))


def normalize(text: str) -> str:
    """Spoken forms -> what the text parsers expect: '45 тысяч такси.' -> '45000 такси'."""
    import re

    text = text.strip().rstrip(".!…").strip()
    text = re.sub(r"(\d)\s+(\d{3})(?!\d)", r"\1\2", text)  # "45 000" -> "45000" before scales
    text = words_to_digits(text)
    # "Задача – купить молоко" -> "Задача: купить молоко"
    text = re.sub(r"^(\w+)\s+[–—-]\s+", r"\1: ", text)

    def millions(m: "re.Match[str]") -> str:
        value = float(m[1].replace(" ", "").replace(",", "."))
        return str(int(round(value * 1_000_000)))

    text = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:миллион[а-я]*|млн\.?)(?=\s|$)", millions, text, flags=re.I)
    text = re.sub(r"(\d)\s*(?:тысяч[а-я]*|тыщ[а-я]*|тыс\.)(?=\s|$)", r"\1 тыс", text, flags=re.I)
    text = re.sub(r"(\d)\s+(\d{3})(?!\d)", r"\1\2", text)  # "45 000" -> "45000"
    return text


def media_of(message: dict) -> Optional[dict]:
    """The voice/audio/round-video object of a message, if any."""
    for key in ("voice", "audio", "video_note"):
        if isinstance(message.get(key), dict):
            return message[key]
    return None


def check_media(media: dict) -> None:
    duration = int(media.get("duration") or 0)
    if duration > settings.voice_max_seconds:
        raise VoiceError(
            f"Голосовое слишком длинное ({duration // 60}:{duration % 60:02d}). "
            f"Я разбираю до {settings.voice_max_seconds // 60} минут — разделите на части."
        )
    if int(media.get("file_size") or 0) > 20 * 1024 * 1024:
        raise VoiceError("Файл больше 20 МБ — Telegram не даёт ботам скачать его.")


async def download(file_id: str, token: Optional[str]) -> bytes:
    if not token:
        raise VoiceError("Бот не подключён — не могу скачать голосовое.")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"https://api.telegram.org/bot{token}/getFile", json={"file_id": file_id})
        r.raise_for_status()
        path = (r.json().get("result") or {}).get("file_path")
        if not path:
            raise VoiceError("Telegram не отдал файл голосового, попробуйте ещё раз.")
        f = await client.get(f"https://api.telegram.org/file/bot{token}/{path}")
        f.raise_for_status()
        return f.content


async def warm_up() -> None:
    """Download the model in the background at start, so the first voice message is not slow."""
    if not settings.voice_enabled:
        return
    try:
        from faster_whisper.utils import download_model

        await asyncio.to_thread(download_model, settings.voice_model, cache_dir=settings.voice_model_dir)
        logger.info("Voice model %s is available", settings.voice_model)
    except Exception as ex:  # no network now: it will be fetched on the first voice message
        logger.warning("Voice model download skipped: %s", ex)
