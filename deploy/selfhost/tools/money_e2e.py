"""Monthly limit + P2P transfers against a throwaway stack (Telegram mocked).

    docker compose -p pos-e2e exec -T -w /app api python - http://127.0.0.1:8000/v1 < tools/money_e2e.py

"лимит" commands; bank notices (P2P and a shop) -> 80%/100% warnings once; P2P marked as
own money / loan / expense (spending recalculated, undo works); evening digest lists
unsorted transfers and its button asks about each; dashboard shows the limit.
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
CHAT = 556000 + uuid.uuid4().int % 1000
sent = []
problems = []


def check(ok, what):
    print(("  ok   " if ok else "  BAD  ") + what)
    if not ok:
        problems.append(what)


async def fake_bot_api(method, payload, bot_token=None):
    sent.append((method, payload))
    return {"ok": True, "result": {"message_id": len(sent)}}


def last_text():
    return sent[-1][1].get("text", "") if sent else ""


def buttons(payload):
    return [b for row in (payload.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]


def uzcard(amount, merchant, when):
    return (f"🔴 Оплата\n➖ {amount} UZS\n📍 {merchant}\n💳 ***{CARD}\n"
            f"🕓 {when.astimezone(TZ):%d.%m.%y %H:%M}\n💰 9.000.000,00 UZS")


CARD = f"{uuid.uuid4().int % 9000 + 1000}"


async def main():
    import src.main  # noqa: F401
    from src.db.session import async_session_factory
    from src.domains.finance.models import Account, BankNotice
    from src.integrations.models import Integration
    from src.integrations.telegram import bank_flow, daily
    from src.integrations.telegram.handler import handle_telegram_update

    email = f"money-{uuid.uuid4().hex[:8]}@example.com"
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.post("/auth/register", json={"email": email, "password": "password123", "full_name": "M", "timezone": "Asia/Tashkent"})
        check(r.status_code == 201, f"register {r.status_code}")
        tok = c.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        ws = uuid.UUID(c.get("/workspaces", headers=H).json()[0]["id"])

    async with async_session_factory() as s:
        s.add(Integration(workspace_id=ws, provider="telegram", status="connected", config={"chat_id": str(CHAT)}))
        await s.commit()

    def msg(text):
        return {"message": {"message_id": 1, "text": text, "chat": {"id": CHAT}, "from": {"id": CHAT}}}

    def cb(data):
        return {"callback_query": {"id": "1", "data": data, "message": {"message_id": 7, "chat": {"id": CHAT}}}}

    now = datetime.now(timezone.utc)
    n = 0

    async def notice(amount, merchant):
        nonlocal n
        n += 1
        when = now - timedelta(minutes=30 - n)
        sent.clear()
        async with async_session_factory() as s:
            await bank_flow.ingest(s, ws, CHAT, "uzcard", uzcard(amount, merchant, when), when, f"e2e-{CHAT}-{n}")
        return sent[-1][1] if sent else {}

    async def alerts(at):
        sent.clear()
        await daily.tick(now=at)
        return [p["text"] for _, p in sent if p.get("chat_id") == str(CHAT) and ("лимит" in p.get("text", "").lower())]

    with patch("src.integrations.telegram.handler._bot_api", fake_bot_api):
        print("# limit command")
        sent.clear()
        await handle_telegram_update(msg("лимит"))
        check("не задан" in last_text(), "no limit yet")
        await handle_telegram_update(msg("лимит 1 млн"))
        check("✅ Лимит на месяц: 1 000 000 сум" in last_text(), f"limit set: {last_text()[:60]!r}")
        await handle_telegram_update(msg("лимит пять"))
        check("Не понял сумму" in last_text(), "bad amount rejected")

        print("# P2P notice")
        p = await notice("500.000,00", "CLICK P2P, UZ")
        labels = [b["text"] for b in buttons(p)]
        check("Это перевод" in p.get("text", "") and "👤 Себе" in labels and "🤝 Дал в долг" in labels,
              f"P2P asks own/loan: {labels}")
        p2p_btn = {b["text"]: b["callback_data"] for b in buttons(p)}
        check(await alerts(now) == [], "50%: no warning")

        print("# shop notice -> 85%")
        p = await notice("350.000,00", "KORZINKA CHILONZOR")
        check("👤 Себе" not in [b["text"] for b in buttons(p)], "shop has no P2P buttons")
        a = await alerts(now)
        check(len(a) == 1 and a[0].startswith("🟨") and "85%" in a[0], f"80% warning: {a}")
        check(await alerts(now + timedelta(minutes=1)) == [], "80% warning not repeated")

        print("# mark P2P as own money")
        sent.clear()
        await handle_telegram_update(cb(p2p_btn["👤 Себе"]))
        check("Перевод себе" in last_text() and "не расход" in last_text(), f"own transfer: {last_text()[-60:]!r}")
        async with async_session_factory() as s:
            own = (await s.execute(select(Account).where(Account.workspace_id == ws, Account.name == bank_flow.OWN_ACCOUNT))).scalar_one()
            check(own.balance_minor == 50_000_000, f"own-money account got 500 000 ({own.balance_minor})")
        sent.clear()
        await handle_telegram_update(msg("лимит"))
        check("350 000 сум из 1 000 000 сум (35%)" in last_text(), f"spending recalculated: {last_text()!r}")

        print("# second P2P -> 105%")
        await notice("700.000,00", "PAYME P2P, UZ")
        a = await alerts(now)
        check(len(a) == 1 and a[0].startswith("🟥"), f"100% warning: {a}")

        print("# evening digest + sort button")
        evening = datetime.combine(datetime.now(TZ).date(), time(21, 5), TZ).astimezone(timezone.utc)
        async with async_session_factory() as s:
            integ = (await s.execute(select(Integration).where(Integration.workspace_id == ws, Integration.provider == "telegram"))).scalar_one()
            integ.config = {**integ.config, "digests_sent": {"morning": datetime.now(TZ).date().isoformat()}}
            await s.commit()
        sent.clear()
        await daily.tick(now=evening)
        ev = [pl for _, pl in sent if pl.get("text", "").startswith("🌙") and pl.get("chat_id") == str(CHAT)]
        check(len(ev) == 1, "evening summary sent")
        if ev:
            t = ev[0]["text"]
            check("🟥 Месяц: 1 050 000 сум из 1 000 000 сум (105%)" in t, "limit line in summary")
            check("Переводы без пометки: 1 на 700 000 сум" in t, "unsorted transfers counted")
            sort = [b for b in buttons(ev[0]) if b["callback_data"] == "dg:p2p"]
            check(len(sort) == 1, "sort transfers button")
            sent.clear()
            await handle_telegram_update(cb("dg:p2p"))
            q = [pl for _, pl in sent if "PAYME P2P" in pl.get("text", "")]
            check(len(q) == 1 and len(buttons(q[0])) == 3, "asked about the unsorted transfer")
            if q:
                debt = next(b["callback_data"] for b in buttons(q[0]) if "долг" in b["text"])
                sent.clear()
                await handle_telegram_update(cb(debt))
                check("Дали в долг" in last_text(), "marked as loan")
                sent.clear()
                await handle_telegram_update(cb("dg:p2p"))
                check("Неразобранных переводов нет" in last_text(), "nothing left to sort")

        print("# back to expense, then undo")
        sent.clear()
        await handle_telegram_update(cb(p2p_btn["🛒 Это расход"]))
        check("Записано: «Переводы» (ваш выбор)" in last_text(), f"own -> expense: {last_text()[-50:]!r}")
        async with async_session_factory() as s:
            own = (await s.execute(select(Account).where(Account.workspace_id == ws, Account.name == bank_flow.OWN_ACCOUNT))).scalar_one()
            check(own.balance_minor == 0, "own-money account back to 0")
        undo = p2p_btn["🛒 Это расход"].rsplit(":", 2)[0] + ":undo"
        await handle_telegram_update(cb(undo))
        check("Отменено" in last_text(), "undo")
        async with async_session_factory() as s:
            st = (await s.execute(select(BankNotice.status).where(BankNotice.workspace_id == ws).order_by(BankNotice.occurred_at))).scalars().all()
            check(st == ["ignored", "posted", "posted"], f"notice states {st}")
        sent.clear()
        await handle_telegram_update(msg("лимит"))
        check("350 000 сум из 1 000 000 сум (35%)" in last_text(), f"loan and undone P2P not counted: {last_text()[:90]!r}")

    with httpx.Client(base_url=BASE, timeout=30) as c:
        b = c.get("/dashboard/today", headers=H).json()["budget_summary"]
        check(b["monthly_limit_minor"] == 100_000_000 and b["monthly_spent_minor"] == 35_000_000, f"dashboard {b}")
    with patch("src.integrations.telegram.handler._bot_api", fake_bot_api):
        await handle_telegram_update(msg("лимит выкл"))
        check("Лимит убран" in last_text(), "limit removed")
    with httpx.Client(base_url=BASE, timeout=30) as c:
        b = c.get("/dashboard/today", headers=H).json()["budget_summary"]
        check(b["monthly_limit_minor"] == 0, "dashboard: no limit")

    print(f"\nRESULT: {'0 problems' if not problems else problems}")


asyncio.run(main())
