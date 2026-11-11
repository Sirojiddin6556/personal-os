"""Real speech recognition on this server (model downloaded on first run).

    docker compose cp v1.wav api:/tmp/voice/ ...   # Russian samples, any format ffmpeg/av can read
    docker compose -p pos-e2e exec -T -w /app api python - /tmp/voice "45000 такси|..." < tools/voice_e2e.py

For each file: converted to Telegram's format (OGG/Opus) when possible, recognized,
normalized and classified exactly like a voice message in the bot. Prints timings.
"""
import asyncio
import io
import pathlib
import sys
import time
import uuid


def to_ogg_opus(raw: bytes) -> bytes:
    import av

    src = av.open(io.BytesIO(raw))
    out_buf = io.BytesIO()
    out = av.open(out_buf, "w", format="ogg")
    stream = out.add_stream("libopus", rate=48000)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
    for frame in src.decode(audio=0):
        for f in resampler.resample(frame):
            for packet in stream.encode(f):
                out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)
    out.close()
    return out_buf.getvalue()


async def main():
    import src.main  # noqa: F401
    from src.integrations.telegram import voice
    from src.integrations.telegram.handler import ai_parse_telegram_message

    folder = pathlib.Path(sys.argv[1])
    expected = sys.argv[2].split("|") if len(sys.argv) > 2 else []
    problems = []
    for i, path in enumerate(sorted(folder.iterdir())):
        raw = path.read_bytes()
        try:
            audio, fmt = to_ogg_opus(raw), "ogg/opus"
        except Exception as ex:  # encoder missing: recognize the original file
            audio, fmt = raw, f"original ({type(ex).__name__})"
        started = time.monotonic()
        text = await voice.engine.transcribe(audio)
        took = time.monotonic() - started
        norm = voice.normalize(text)
        intent = await ai_parse_telegram_message(norm, uuid.uuid4())
        want = expected[i] if i < len(expected) else ""
        if want == "LIMIT":  # handled before intents, like in the bot
            from src.domains.finance.limits import parse_limit_amount
            from src.integrations.telegram.daily import LIMIT_RE

            m = LIMIT_RE.match(norm)
            intent.type, intent.data = ("LIMIT", {"minor": parse_limit_amount(m[1])}) if m else (intent.type, intent.data)
        ok = not want or intent.type == want
        print(f"{'ok ' if ok else 'BAD'} {path.name} [{fmt}, {len(audio)} B] {took:.1f}s\n"
              f"    heard: {text!r}\n    parsed: {intent.type} {intent.data}")
        if not ok:
            problems.append(path.name)
    print(f"\nRESULT: {'0 problems' if not problems else problems}")


asyncio.run(main())
