"""Weekly review + GitHub issues -> tasks against a throwaway stack (Telegram and GitHub mocked).

    docker compose -p pos-e2e exec -T -w /app api python - http://127.0.0.1:8000/v1 < tools/phase3_e2e.py
"""
import asyncio
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1"
TZ = ZoneInfo("Asia/Tashkent")
CHAT = 557000 + uuid.uuid4().int % 1000
sent = []
problems = []


def check(ok, what):
    print(("  ok   " if ok else "  BAD  ") + what)
    if not ok:
        problems.append(what)


async def fake_bot_api(method, payload, bot_token=None):
    sent.append((method, payload))
    return {"ok": True, "result": {"message_id": len(sent)}}


def mine():
    return [p for _, p in sent if p.get("chat_id") in (CHAT, str(CHAT))]


async def main():
    import src.main  # noqa: F401
    from src.db.session import async_session_factory
    from src.domains.finance.schemas import AccountCreate, TransactionCreate
    from src.domains.finance.service import finance_service
    from src.domains.planner.models import Habit, HabitLog
    from src.domains.projects.models import Project
    from src.domains.tasks.models import Task
    from src.integrations.github import scheduler as gh
    from src.integrations.github.service import github_service
    from src.integrations.models import Integration
    from src.integrations.telegram import daily
    from src.integrations.telegram.handler import handle_telegram_update

    email = f"week-{uuid.uuid4().hex[:8]}@example.com"
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.post("/auth/register", json={"email": email, "password": "password123", "full_name": "W", "timezone": "Asia/Tashkent"})
        check(r.status_code == 201, f"register {r.status_code}")
        tok = c.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
        ws = uuid.UUID(c.get("/workspaces", headers={"Authorization": f"Bearer {tok}"}).json()[0]["id"])

    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ).date()
    sunday = today + timedelta(days=6 - today.weekday())
    async with async_session_factory() as s:
        s.add(Integration(workspace_id=ws, provider="telegram", status="connected", config={"chat_id": str(CHAT)}))
        s.add(Integration(workspace_id=ws, provider="github", status="connected", config={"login": "e2e"}))
        s.add(Task(workspace_id=ws, title="Закрыть квартал", status="done", priority="medium", completed_at=now))
        s.add(Task(workspace_id=ws, title="Оплатить налог", status="todo", priority="high", due_at=now - timedelta(days=1)))
        habit = Habit(workspace_id=ws, title="Зарядка")
        s.add(habit)
        await s.flush()
        s.add(HabitLog(workspace_id=ws, habit_id=habit.id, logged_date=today))
        proj = Project(workspace_id=ws, name="demo", github_repo="e2e/demo", github_default_branch="main",
                       status="active", color="#3B82F6")
        s.add(proj)
        await s.commit()
        acc = await finance_service.create_account(s, ws, AccountCreate(name="Карта", type="checking", currency="UZS"))
        await finance_service.post_transaction(s, ws, TransactionCreate(
            account_id=acc.id, amount_minor=12_000_000, currency="UZS", transaction_type="expense",
            note="обед", occurred_at=now))
        await s.commit()

    with patch("src.integrations.telegram.handler._bot_api", fake_bot_api):
        print("# weekly review")
        at = datetime.combine(sunday, time(20, 5), TZ).astimezone(timezone.utc)
        async with async_session_factory() as s:
            integ = (await s.execute(select(Integration).where(Integration.workspace_id == ws, Integration.provider == "telegram"))).scalar_one()
            integ.config = {**integ.config, "digests_sent": {"morning": sunday.isoformat()}}
            await s.commit()
        sent.clear()
        await daily.tick(now=at)
        wk = [p for p in mine() if p.get("text", "").startswith("📆")]
        check(len(wk) == 1, "weekly review sent on Sunday 20:05")
        if wk:
            t = wk[0]["text"]
            check("✅ Сделано задач: 1" in t and "Закрыть квартал" in t, "done this week")
            check("⚠️ Просрочено сейчас: 1" in t and "Оплатить налог" in t, "overdue")
            check("Потрачено за неделю: 120 000 сум" in t, "week spending")
            check("• Зарядка: 1 из 7" in t, "habits")
            cb = wk[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
            check(cb == f"dg:carry:{sunday:%Y%m%d}", "carry-to-Monday button")
        sent.clear()
        await daily.tick(now=at + timedelta(minutes=10))
        check(not [p for p in mine() if p.get("text", "").startswith("📆")], "weekly not repeated")

        print("# GitHub issues -> tasks")
        issues = [
            {"number": 1, "title": "Падает экспорт", "state": "open", "html_url": "https://github.com/e2e/demo/issues/1"},
            {"number": 2, "title": "Тёмная тема", "state": "open", "html_url": "https://github.com/e2e/demo/issues/2"},
            {"number": 3, "title": "Старое", "state": "closed", "html_url": "https://github.com/e2e/demo/issues/3"},
            {"number": 4, "title": "PR", "state": "open", "pull_request": {}, "html_url": "https://github.com/e2e/demo/pull/4"},
        ]
        client = AsyncMock()
        client.list_issues.side_effect = lambda *a, **k: [dict(i) for i in issues]
        with patch.object(github_service, "get_client", AsyncMock(return_value=client)):
            sent.clear()
            n = await gh.sync_workspace(ws)
            check(n == (2, 0), f"2 new tasks, PR and old closed issue skipped {n}")
            check(any("🐙 Новые задачи из GitHub: 2" in p.get("text", "") for p in mine()), "Telegram notice")
            sent.clear()
            n = await gh.sync_workspace(ws)
            check(n == (0, 0) and not mine(), "second pass: nothing new, no message")

            issues[0]["state"] = "closed"
            issues[1]["title"] = "Тёмная тема в мини-приложении"
            n = await gh.sync_workspace(ws)
            check(n == (0, 1), f"closed issue closes its task {n}")
            async with async_session_factory() as s:
                rows = {t.title: t for t in (await s.execute(select(Task).where(Task.workspace_id == ws, Task.project_id == proj.id))).scalars()}
            check(rows.get("[#1] Падает экспорт") is not None and rows["[#1] Падает экспорт"].status == "done", "task #1 done")
            check("[#2] Тёмная тема в мини-приложении" in rows, "renamed issue renames task")

            async with async_session_factory() as s:
                t2 = (await s.execute(select(Task).where(Task.workspace_id == ws, Task.title.like("[#2]%")))).scalar_one()
                t2.is_deleted = True
                await s.commit()
            n = await gh.sync_workspace(ws)
            async with async_session_factory() as s:
                live = (await s.execute(select(Task).where(Task.workspace_id == ws, Task.title.like("[#2]%"), Task.is_deleted.is_(False)))).scalars().all()
            check(n == (0, 0) and not live, "task deleted here is not brought back")

    print(f"\nRESULT: {'0 problems' if not problems else problems}")


asyncio.run(main())
