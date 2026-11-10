"""End-to-end check of the fully automatic bank flow against a real Postgres.

Run inside the api container of a THROWAWAY stack (Telegram calls are mocked):
    docker compose -p pos-e2e exec -T -w /app api python - http://127.0.0.1:8000/v1 < tools/bank_e2e.py
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
    token = b["access_token"]
    s, wss = api("GET", "/workspaces", token=token)
    return token, wss[0]["id"]


HUMO = "💸 Оплата\n➖ 101.100,00 UZS\n📍 KORZINKA CHILANZAR\n💳 HUMOCARD *1234\n🕓 11:39 15.10.2026\n💰 301.077,41 UZS"
UZ_OUT = "🔴 Списание\n➖ 100 000.00 UZS\n💳 ***5678\n📍 PAYME P2P FROM UZCARD TO HUMO\n🕓 15.10.26 12:00\n💵 81 000.00 UZS"
HUMO_IN = "💸 Пополнение\n➕ 100.000,00 UZS\n📍 PAYME P2P U2H\n💳 HUMOCARD *1234\n🕓 12:01 15.10.2026\n💰 1.000,00 UZS"


def fwd(text, date, username="HumoCardBot", uid=111):
    return {"message": {"message_id": 1, "text": text, "chat": {"id": 777}, "from": {"id": 777},
                        "forward_origin": {"type": "user", "date": date,
                                           "sender_user": {"id": uid, "is_bot": True, "username": username}}}}


def cb(data, mid=50):
    return {"callback_query": {"id": "c", "data": data, "message": {"message_id": mid, "chat": {"id": 777}}}}


async def main():
    from src.integrations.telegram import handler

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

    async def send(update, ws_id=W):
        sent.clear()
        await handler.handle_telegram_update(update, workspace_id=ws_id)

    def accounts():
        s, a = api("GET", "/finance/accounts", token=tok, ws=ws)
        return {x.get("card_last4") or x["name"]: x for x in (a if isinstance(a, list) else a.get("items", []))}

    def txs():
        s, t = api("GET", "/finance/transactions?limit=100", token=tok, ws=ws)
        return t if isinstance(t, list) else t.get("items", [])

    print("# 1. new card + known shop: account and category created, nothing asked")
    await send(fwd(HUMO, 1760000001))
    t = last().get("text", "")
    check("✅ Записано" in t and "Продукты" in t, f"auto-posted as Продукты ({t[-60:]!r})")
    acc = accounts().get("1234")
    check(acc is not None and acc["name"] == "HUMO *1234", "account HUMO *1234 auto-created")
    check(acc and acc["current_balance_minor"] == -10110000, "balance -101 100")
    check({b["callback_data"].split(":")[-1] for b in buttons()} == {"edit", "undo"}, "only edit/undo buttons")

    print("# 2. duplicate forward ignored")
    await send(fwd(HUMO, 1760000001))
    check("уже было" in last().get("text", ""), "duplicate detected")
    check(accounts()["1234"]["current_balance_minor"] == -10110000, "balance unchanged")

    print("# 3. correction re-categorizes and is learned")
    edit = next(b for b in buttons() if True) if False else None
    await send(fwd(HUMO.replace("101.100,00", "20.000,00"), 1760000002))
    edit = next(b for b in buttons() if b["callback_data"].endswith(":edit"))
    await send(cb(edit["callback_data"]))
    names = [b["text"] for b in buttons()]
    check(any("Продукты" in n for n in names), f"category choices shown {names[:4]}")
    await send(cb(edit["callback_data"].replace(":edit", ":c:0")))  # first option (current) just to exercise path
    await send(fwd(HUMO.replace("101.100,00", "30.000,00"), 1760000003))
    edit = next(b for b in buttons() if b["callback_data"].endswith(":edit"))
    s, _ = api("POST", "/finance/categories", {"name": "Супермаркеты", "type": "expense"}, token=tok, ws=ws)
    await send(cb(edit["callback_data"]))
    target = next((b for b in buttons() if "Супермаркеты" in b["text"]), None)
    check(target is not None, "new category offered")
    await send(cb(target["callback_data"]))
    check("Супермаркеты" in last().get("text", "") and "ваш выбор" in last().get("text", ""), "re-posted under chosen category")
    check(accounts()["1234"]["current_balance_minor"] == -15110000, "balance correct after re-categorize (no double count)")
    await send(fwd(HUMO.replace("101.100,00", "5.000,00"), 1760000004))
    t = last().get("text", "")
    check("Супермаркеты" in t and "как вы выбирали раньше" in t, "next KORZINKA uses the learned category")

    print("# 4. own-card transfer is detected (not expense + income)")
    await send(fwd(UZ_OUT, 1760100000, username="CardXabarBot", uid=915326936))
    check("Переводы" in last().get("text", ""), "first leg posted as Переводы")
    before = accounts()
    await send(fwd(HUMO_IN, 1760100060))
    t = last().get("text", "")
    check("🔁 Перевод между своими картами" in t, f"pair detected ({t[:60]!r})")
    after = accounts()
    check(after["5678"]["current_balance_minor"] == -10000000, "Uzcard -100 000 (one transfer)")
    check(after["1234"]["current_balance_minor"] == before["1234"]["current_balance_minor"] + 10000000, "HUMO +100 000")
    kinds = [x["type"] for x in txs() if x["amount_minor"] == 10000000]
    check(kinds.count("transfer") == 1, f"one transfer transaction ({kinds})")
    undo = next(b for b in buttons() if b["callback_data"].endswith(":undo"))
    await send(cb(undo["callback_data"]))
    end = accounts()
    check(end["5678"]["current_balance_minor"] == 0 and end["1234"]["current_balance_minor"] == before["1234"]["current_balance_minor"],
          "undo restores both cards")

    print("# 5. ads/balances skipped quietly via listener mode, loud via forward")
    await send(fwd("Ваш баланс: 💰 1 000 000 UZS", 1760200000))
    check("пропустил" in last().get("text", ""), "balance-only skipped")

    print("# 6. manual text expense recorded at once")
    await send({"message": {"text": "45000 taksi", "chat": {"id": 777}, "from": {"id": 777}}})
    t = last().get("text", "")
    check("✅ Записано" in t and "Такси" in t, f"manual auto-category ({t!r})")
    check("Наличные" in accounts(), "cash account auto-created")
    undo = buttons()[0]["callback_data"]
    await send(cb(undo))
    check("Отменено" in last().get("text", ""), "manual undo")
    check(accounts()["Наличные"]["current_balance_minor"] == 0, "cash balance restored")

    print("# 7. isolation")
    await send(fwd(HUMO.replace("101.100,00", "7.000,00"), 1760300000))
    foreign = buttons()[0]["callback_data"]
    await send(cb(foreign), ws_id=UUID(ws_b))
    check("не найдено" in last().get("text", ""), "B cannot touch A's notice")
    s, a = api("GET", "/finance/accounts", token=tok_b, ws=ws_b)
    check(not (a if isinstance(a, list) else a.get("items", [])), "B has no accounts")

    print(f"\nRESULT: {OK} ok, {len(PROBLEMS)} problems")
    for p in PROBLEMS:
        print(" -", p)


asyncio.run(main())
