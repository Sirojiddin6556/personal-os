"""Daily Telegram loop against a throwaway stack (Telegram mocked).

    docker compose -p pos-e2e exec -T -w /app api python - http://127.0.0.1:8000/v1 < tools/daily_e2e.py

Unknown text -> inbox buttons -> task; expense; morning/evening digests (once per day);
"move to tomorrow"; calendar event reminder 15 minutes ahead (once).
"""
import asyncio
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1"
TZ = ZoneInfo("Asia/Tashkent")
CHAT = 555000 + uuid.uuid4().int % 1000
sent = []
problems = []


def check(ok, what):
    print(("  ok   " if ok else "  BAD  ") + what)
    if not ok:
        problems.append(what)


async def fake_bot_api(method, payload, bot_token=None):
    sent.append((method, payload))
    return {"ok": True, "result": {"message_id": len(sent)}}


async def main():
    import src.main  # noqa: F401  (registers every ORM model)
    from src.db.session import async_session_factory
    from src.domains.calendar.models import Event
    from src.domains.tasks.models import Task
    from src.integrations.models import InboxItem, Integration
    from src.integrations.telegram import daily
    from src.integrations.telegram.handler import handle_telegram_update

    email = f"daily-{uuid.uuid4().hex[:8]}@example.com"
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.post("/auth/register", json={"email": email, "password": "password123", "full_name": "D", "timezone": "Asia/Tashkent"})
        check(r.status_code == 201, f"register {r.status_code}")
        tok = c.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
        ws = uuid.UUID(c.get("/workspaces", headers={"Authorization": f"Bearer {tok}"}).json()[0]["id"])

    today = datetime.now(TZ).date()
    async with async_session_factory() as s:
        s.add(Integration(workspace_id=ws, provider="telegram", status="connected", config={"chat_id": str(CHAT)}))
        s.add(Task(workspace_id=ws, title="Сдать отчёт", status="todo", priority="medium",
                   due_at=datetime.combine(today, time(15, 0), TZ)))
        s.add(Task(workspace_id=ws, title="Оплатить интернет", status="todo", priority="medium",
                   due_at=datetime.combine(today - timedelta(days=2), time(10, 0), TZ)))
        s.add(Event(workspace_id=ws, title="Планёрка", starts_at=datetime.combine(today, time(9, 30), TZ),
                    ends_at=datetime.combine(today, time(10, 0), TZ)))
        await s.commit()

    def upd(text=None, data=None):
        if data:
            return {"callback_query": {"id": "1", "data": data, "message": {"message_id": 1, "chat": {"id": CHAT}}}}
        return {"message": {"message_id": 1, "text": text, "chat": {"id": CHAT}, "from": {"id": CHAT}}}

    with patch("src.integrations.telegram.handler._bot_api", fake_bot_api):
        print("# capture")
        sent.clear()
        await handle_telegram_update(upd("позвонить Акмалю по davomat"))
        msg = sent[-1][1]
        check("Входящие" in msg["text"], "unknown text saved to inbox, not 'Не понял'")
        cb = msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        await handle_telegram_update(upd(data=cb))
        check(any("Задача: позвонить Акмалю" in p.get("text", "") for _, p in sent), "button -> task created")
        await handle_telegram_update(upd(data=cb))
        check("уже разобрана" in sent[-1][1]["text"], "second tap does nothing")
        await handle_telegram_update(upd("45000 такси"))
        check("Записано: 45 000" in sent[-1][1]["text"], "expense recorded")
        await handle_telegram_update(upd("привет"))
        async with async_session_factory() as s:
            pending = (await s.execute(select(InboxItem).where(InboxItem.workspace_id == ws, InboxItem.status == "pending"))).scalars().all()
        check(len(pending) == 0, f"expense/greeting/sorted items are not 'pending' ({len(pending)})")

        print("# digests")
        seen = daily._Seen()
        morning = datetime.combine(today, time(8, 1), TZ).astimezone(timezone.utc)
        sent.clear()
        await daily.tick(now=morning, seen=seen)
        texts = [p["text"] for _, p in sent if p.get("chat_id") == str(CHAT)]
        check(len(texts) == 1 and texts[0].startswith("☀️"), "morning brief sent")
        t = texts[0] if texts else ""
        check("09:30–10:00 Планёрка" in t, "today's event in local time")
        check("Просрочено (1)" in t and "Оплатить интернет" in t, "overdue task")
        check("Задачи на сегодня (1)" in t and "Сдать отчёт" in t, "task due today")
        sent.clear()
        await daily.tick(now=morning + timedelta(minutes=5), seen=seen)
        check(not [p for _, p in sent if "☀️" in p.get("text", "")], "morning brief not repeated")

        evening = datetime.combine(today, time(21, 0), TZ).astimezone(timezone.utc)
        sent.clear()
        await daily.tick(now=evening, seen=seen)
        ev = [p for _, p in sent if p.get("text", "").startswith("🌙") and p.get("chat_id") == str(CHAT)]
        check(len(ev) == 1, "evening summary sent")
        if ev:
            check("Потрачено сегодня: 45 000 сум" in ev[0]["text"], "today's spending in summary")
            carry = ev[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
            await handle_telegram_update(upd(data=carry))
            check("Перенёс на завтра: 2" in sent[-1][1]["text"], f"carry over: {sent[-1][1]['text']}")
            async with async_session_factory() as s:
                dues = (await s.execute(select(Task.due_at).where(Task.workspace_id == ws, Task.due_at.is_not(None)))).scalars().all()
            check(all(d.astimezone(TZ).date() == today + timedelta(days=1) for d in dues), "tasks moved to tomorrow")

        print("# event reminder")
        now = datetime.now(timezone.utc)
        async with async_session_factory() as s:
            s.add(Event(workspace_id=ws, title="Созвон с заказчиком", location="Zoom",
                        starts_at=now + timedelta(minutes=10), ends_at=now + timedelta(minutes=40)))
            await s.commit()
        sent.clear()
        await daily.tick(now=now, seen=seen)
        rem = [p for _, p in sent if "Созвон с заказчиком" in p.get("text", "")]
        check(len(rem) == 1 and "Через 10 мин" in rem[0]["text"], "reminder 10 min before event")
        sent.clear()
        await daily.tick(now=now + timedelta(minutes=1), seen=seen)
        check(not [p for _, p in sent if "Созвон" in p.get("text", "")], "event reminder not repeated")

    print(f"\nRESULT: {'0 problems' if not problems else problems}")


asyncio.run(main())
