"""End-to-end check of forwarded bank notices against a real Postgres (run inside the api container).

Usage: python - <api base url>   (registers two throwaway users via the API)
"""
import asyncio
import json
import sys
import time
import urllib.request
from uuid import UUID

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1"
PROBLEMS = []
OK = 0


def check(cond, label):
    global OK
    if cond:
        OK += 1
        print("  ok  ", label)
    else:
        PROBLEMS.append(label)
        print("  FAIL", label)


def api(method, path, body=None, token=None, ws=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if ws:
        req.add_header("X-Workspace-Id", ws)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode()


def register(tag):
    email = f"bank-{tag}-{int(time.time()*1000)}@example.com"
    s, b = api("POST", "/auth/register", {"email": email, "password": "Passw0rd!x", "full_name": f"User {tag}"})
    assert s == 201, (s, b)
    s, b = api("POST", "/auth/login", {"email": email, "password": "Passw0rd!x"})
    assert s == 200, (s, b)
    token = b["access_token"]
    s, wss = api("GET", "/workspaces", token=token)
    return token, wss[0]["id"]


HUMO = "💸 Оплата\n➖ 101.100,00 UZS\n📍 KORZINKA CHILANZAR\n💳 HUMOCARD *1234\n🕓 11:39 15.10.2026\n💰 301.077,41 UZS"


def fwd(text, date, username="HumoCardBot", uid=111, is_bot=True):
    return {"message": {"message_id": 1, "text": text, "chat": {"id": 777}, "from": {"id": 777},
                        "forward_origin": {"type": "user", "date": date,
                                           "sender_user": {"id": uid, "is_bot": is_bot, "username": username}}}}


def cb(data, mid=50):
    return {"callback_query": {"id": "c", "data": data, "message": {"message_id": mid, "chat": {"id": 777}}}}


async def main():
    from src.integrations.telegram import handler
    from src.db.session import async_session_factory
    from sqlalchemy import text as sql

    sent = []

    async def fake_api(method, payload, bot_token=None):
        sent.append((method, payload))
        return {"ok": True, "result": {"message_id": 50}}

    handler._bot_api = fake_api

    tok, ws = register("a")
    tok_b, ws_b = register("b")
    W = UUID(ws)

    def last():
        return sent[-1][1] if sent else {}

    def buttons():
        kb = (last().get("reply_markup") or {}).get("inline_keyboard") or []
        return [b for row in kb for b in row]

    async def send(update):
        sent.clear()
        await handler.handle_telegram_update(update, workspace_id=W)

    async def balance(acc_id):
        s, accs = api("GET", "/finance/accounts", token=tok, ws=ws)
        items = accs if isinstance(accs, list) else accs.get("items", [])
        return next(a for a in items if a["id"] == acc_id)["current_balance_minor"]

    # setup: categories + account without card
    for name in ("Продукты", "Кафе и рестораны", "Такси"):
        s, _ = api("POST", "/finance/categories", {"name": name, "type": "expense"}, token=tok, ws=ws)
    s, acc = api("POST", "/finance/accounts", {"name": "Наличные", "type": "cash", "currency": "UZS", "initial_balance_minor": 0}, token=tok, ws=ws)
    check(s in (200, 201), "account created")

    print("\n# 1. pasted (not forwarded) notice is refused")
    await send({"message": {"text": HUMO, "chat": {"id": 777}, "from": {"id": 777}}})
    check("Перешлите" in last().get("text", ""), "pasted text -> forward hint")

    print("\n# 2. fake bot is ignored as bank notice")
    await send(fwd(HUMO, 1760000000, username="HumoCardBot_fake"))
    check("Перешлите" in last().get("text", ""), "look-alike bot not trusted")

    print("\n# 3. unknown card -> ask account -> new account bound to card")
    await send(fwd(HUMO, 1760000001))
    t = last().get("text", "")
    check("*1234" in t and "не привязана" in t, "asks which account for *1234")
    new_btn = next((b for b in buttons() if b["callback_data"].endswith(":new")), None)
    check(new_btn is not None, "offers new account button")
    await send(cb(new_btn["callback_data"]))
    check(sent and sent[-1][0] == "editMessageText", "edits the same message")
    names = [b["text"] for b in buttons()]
    check(any("Продукты" in n for n in names), f"category buttons shown {names}")
    s, accs = api("GET", "/finance/accounts", token=tok, ws=ws)
    items = accs if isinstance(accs, list) else accs.get("items", [])
    card_acc = next((a for a in items if a.get("card_last4") == "1234"), None)
    check(card_acc is not None and card_acc["name"] == "HUMO *1234", "account HUMO *1234 created with card_last4")

    print("\n# 4. choose category -> posted with bank time, balance changes")
    prod = next(b for b in buttons() if "Продукты" in b["text"])
    await send(cb(prod["callback_data"]))
    check("✅ Записано" in last().get("text", ""), "posted")
    check(await balance(card_acc["id"]) == -10110000, "balance -101 100 sum")
    s, txs = api("GET", "/finance/transactions?limit=10", token=tok, ws=ws)
    items = txs if isinstance(txs, list) else txs.get("items", [])
    tx = next((x for x in items if x["amount_minor"] == 10110000), None)
    check(tx is not None and tx["occurred_at"].startswith("2026-10-15T06:39"), f"occurred_at from notice {tx and tx['occurred_at']}")

    print("\n# 5. double tap and duplicate forward do nothing")
    await send(cb(prod["callback_data"]))
    check("уже обработано" in last().get("text", ""), "second tap refused")
    await send(fwd(HUMO, 1760000001))
    check("уже было" in last().get("text", ""), "same notice forwarded again -> duplicate")
    check(await balance(card_acc["id"]) == -10110000, "balance unchanged after duplicates")

    print("\n# 6. learning: 3 more confirmations -> 4th auto")
    for i in range(2, 5):
        await send(fwd(HUMO.replace("101.100,00", f"{i}0.000,00"), 1760000100 + i))
        t = last().get("text", "")
        check("*1234 → «HUMO *1234»" in t, f"notice {i} routed by card")
        first = buttons()[0]
        check(first["text"].startswith("⭐") and "Продукты" in first["text"], f"learned category first ({first['text']})")
        await send(cb(first["callback_data"]))
    await send(fwd(HUMO.replace("101.100,00", "55.000,00"), 1760000200))
    t = last().get("text", "")
    check("🤖 Записано автоматически" in t and "Продукты" in t, "5th notice saved automatically")
    undo = next((b for b in buttons() if b["callback_data"].endswith(":undo")), None)
    noauto = next((b for b in buttons() if b["callback_data"].endswith(":noauto")), None)
    check(undo is not None and noauto is not None, "undo / stop-auto offered")
    before = await balance(card_acc["id"])
    await send(cb(undo["callback_data"]))
    check(await balance(card_acc["id"]) == before + 5500000, "undo restored balance (reversal)")
    check(any(b["callback_data"].endswith(":c:0") for b in buttons()), "after undo asks category again")
    kafe = next(b for b in buttons() if "Кафе" in b["text"])
    await send(cb(kafe["callback_data"]))
    check("Кафе" in last().get("text", ""), "re-posted under another category")
    await send(fwd(HUMO.replace("101.100,00", "12.000,00"), 1760000300))
    check("автоматически" not in last().get("text", ""), "different choice reset auto rule")

    print("\n# 7. P2P / transfers never learn, uzcard + income")
    p2p = HUMO.replace("KORZINKA CHILANZAR", "PAYME P2P H2U>TASHKE")
    await send(fwd(p2p, 1760000400))
    check(not buttons()[0]["text"].startswith("⭐"), "P2P has no learned suggestion")
    uz = "🟢 Пополнение\n➕ 2 000 000.00 UZS\n💳 ***5678\n📍 SALARY\n🕓 19.10.26 08:16\n💵 2 081 000.00 UZS"
    await send(fwd(uz, 1760000500, username="CardXabarBot", uid=915326936))
    t = last().get("text", "")
    check("Uzcard *5678" in t and "➕ 2 000 000" in t, "uzcard income parsed, asks account")
    await send(fwd(uz, 1760000501, username="CardXabarBot", uid=12345))
    check("Перешлите" in last().get("text", ""), "uzcard look-alike id refused")
    skip = next(b for b in buttons() if b["callback_data"].endswith(":x")) if buttons() else None
    await send(fwd("Ваш баланс: 💰 1 000 000 UZS", 1760000600))
    check("пропустил" in last().get("text", ""), "balance-only notice skipped")

    print("\n# 8. manual text uses fuzzy + learned category")
    await send({"message": {"text": "45000 rfat", "chat": {"id": 777}, "from": {"id": 777}}})
    check("Кафе и рестораны" in last().get("text", ""), f"'rfat' -> Кафе ({last().get('text')})")
    cbdata = buttons()[0]["callback_data"]
    await send(cb(cbdata))
    check("Записано" in last().get("text", ""), "manual expense recorded")
    s, txs = api("GET", "/finance/transactions?limit=50", token=tok, ws=ws)
    items = txs if isinstance(txs, list) else txs.get("items", [])
    manual = next((x for x in items if x["amount_minor"] == 4500000), None)
    check(manual is not None and (manual.get("category_name") or manual.get("category")) == "Кафе и рестораны", "manual tx has fuzzy category")

    print("\n# 9. isolation: workspace B cannot press A's buttons")
    await send(fwd(HUMO.replace("101.100,00", "7.000,00"), 1760000700))
    btn = buttons()[0]["callback_data"]
    sent.clear()
    await handler.handle_telegram_update(cb(btn), workspace_id=UUID(ws_b))
    check("не найдено" in last().get("text", ""), "foreign workspace gets 'not found'")
    async with async_session_factory() as s:
        n = (await s.execute(sql("select count(*) from bank_notices where workspace_id = :w"), {"w": ws_b})).scalar()
    check(n == 0, "B has no notices")

    s, accs = api("GET", "/finance/accounts", token=tok_b, ws=ws_b)
    items = accs if isinstance(accs, list) else accs.get("items", [])
    check(all(a.get("card_last4") != "1234" for a in items), "B does not see A's card account")

    print(f"\nRESULT: {OK} ok, {len(PROBLEMS)} problems")
    for p in PROBLEMS:
        print(" -", p)


asyncio.run(main())
