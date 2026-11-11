"""Invitations against a FRESH throwaway stack with ALLOW_REGISTRATION=false (Telegram mocked).

    docker compose -p pos-e2e exec -T -w /app api python - http://127.0.0.1:8000/v1 < tools/invites_e2e.py

Owner (first account) creates a link in Telegram -> the link opens sign-up once ->
the new person gets an isolated workspace; reuse, bad codes, revoke and non-owners are refused.
"""
import asyncio
import re
import sys
import uuid
from unittest.mock import patch

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1"
problems = []
sent = []


def check(ok, what):
    print(("  ok   " if ok else "  BAD  ") + what)
    if not ok:
        problems.append(what)


async def fake_bot_api(method, payload, bot_token=None):
    sent.append((method, payload))
    return {"ok": True, "result": {"message_id": len(sent)}}


def reg(c, email, invite=None):
    body = {"email": email, "password": "password123", "full_name": email.split("@")[0], "timezone": "Asia/Tashkent"}
    if invite:
        body["invite_code"] = invite
    return c.post("/auth/register", json=body)


def login(c, email):
    tok = c.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


async def main():
    import src.main  # noqa: F401
    from src.db.session import async_session_factory
    from src.integrations.models import Integration
    from src.integrations.telegram.handler import handle_telegram_update

    owner, guest, other = (f"{p}-{uuid.uuid4().hex[:6]}@example.com" for p in ("owner", "guest", "other"))
    OWNER_CHAT, GUEST_CHAT = 558001, 558002
    c = httpx.Client(base_url=BASE, timeout=30)

    print("# closed sign-up")
    check(c.get("/auth/config").json()["registration_enabled"] is True, "fresh server: first account allowed")
    check(reg(c, owner).status_code == 201, "owner registered (first account)")
    check(c.get("/auth/config").json()["registration_enabled"] is False, "then sign-up closes")
    r = reg(c, other)
    check(r.status_code == 403, f"stranger refused ({r.status_code})")
    H1 = login(c, owner)
    ws1 = c.get("/workspaces", headers=H1).json()[0]["id"]
    c.post("/tasks", headers={**H1, "Idempotency-Key": str(uuid.uuid4())}, json={"title": "Секрет владельца"})

    async with async_session_factory() as s:
        s.add(Integration(workspace_id=uuid.UUID(ws1), provider="telegram", status="connected",
                          config={"chat_id": str(OWNER_CHAT), "public_url": "https://e2e.trycloudflare.com"}))
        await s.commit()

    def msg(chat, text):
        return {"message": {"message_id": 1, "text": text, "chat": {"id": chat}, "from": {"id": chat}}}

    def cb(chat, data):
        return {"callback_query": {"id": "1", "data": data, "message": {"message_id": 3, "chat": {"id": chat}}}}

    with patch("src.integrations.telegram.handler._bot_api", fake_bot_api):
        print("# invite from Telegram")
        sent.clear()
        await handle_telegram_update(msg(OWNER_CHAT, "пригласить Акмаль"))
        texts = [p.get("text", "") for _, p in sent]
        link = re.search(r"https://e2e\.trycloudflare\.com/login\?invite=([\w-]+)", texts[0] if texts else "")
        check(bool(link) and "для «Акмаль»" in texts[0], "owner gets a link")
        check(len(texts) == 2 and "@BotFather" in texts[1], "plus a text to forward")
        code = link[1] if link else "x"

        cfg = c.get("/auth/config", params={"invite": code}).json()
        check(cfg == {"registration_enabled": True, "invite_valid": True}, f"link opens sign-up {cfg}")
        check(c.get("/auth/config", params={"invite": "nope"}).json()["invite_valid"] is False, "bad code rejected")
        r = reg(c, other, invite="nope")
        check(r.status_code == 403, "register with bad code refused")

        print("# sign-up with the invite")
        r = reg(c, guest, invite=code)
        check(r.status_code == 201, f"guest registered ({r.status_code})")
        r = reg(c, other, invite=code)
        check(r.status_code == 403, "same link can't be used twice")
        H2 = login(c, guest)
        ws2 = c.get("/workspaces", headers=H2).json()
        check(len(ws2) == 1 and ws2[0]["id"] != ws1, "guest has an own workspace")
        tasks = c.get("/tasks", headers=H2).json()
        items = tasks.get("items", tasks) if isinstance(tasks, dict) else tasks
        check(not any("Секрет" in t.get("title", "") for t in items), "guest sees none of the owner's data")

        print("# only the owner can invite")
        async with async_session_factory() as s:
            s.add(Integration(workspace_id=uuid.UUID(ws2[0]["id"]), provider="telegram", status="connected",
                              config={"chat_id": str(GUEST_CHAT), "public_url": "https://e2e.trycloudflare.com"}))
            await s.commit()
        sent.clear()
        await handle_telegram_update(msg(GUEST_CHAT, "пригласить друга"))
        check("только владелец" in (sent[-1][1].get("text", "") if sent else ""), "guest cannot invite")

        print("# list + revoke")
        sent.clear()
        await handle_telegram_update(msg(OWNER_CHAT, "пригласить Маму"))
        code2 = re.search(r"invite=([\w-]+)", sent[0][1]["text"])[1]
        sent.clear()
        await handle_telegram_update(msg(OWNER_CHAT, "приглашения"))
        listing = sent[-1][1]
        check("Маму" in listing["text"] and "Акмаль" not in listing["text"], "list shows only active ones")
        revoke = listing["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        await handle_telegram_update(cb(OWNER_CHAT, revoke))
        check("отозвано" in sent[-1][1].get("text", ""), "revoked")
        check(c.get("/auth/config", params={"invite": code2}).json()["invite_valid"] is False, "revoked link dead")
        check(reg(c, other, invite=code2).status_code == 403, "revoked link can't register")

    print(f"\nRESULT: {'0 problems' if not problems else problems}")


asyncio.run(main())
