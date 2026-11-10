"""End-to-end audit against a throwaway Personal OS stack (run inside the api container).

Flags: any 5xx, unexpected status codes, data not persisted, and cross-tenant
access (user B touching user A's objects).
"""
import io
import json
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1"
GW = sys.argv[2] if len(sys.argv) > 2 else None
problems = []
log = []


def rec(ok, what, resp=None, note=""):
    status = resp.status_code if resp is not None else "-"
    body = ""
    if resp is not None and not ok:
        body = resp.text[:300].replace("\n", " ")
    line = f"{'OK ' if ok else 'BAD'} {status} {what} {note} {body}".rstrip()
    log.append(line)
    if not ok:
        problems.append(line)


class Client:
    def __init__(self, name):
        self.name = name
        self.c = httpx.Client(base_url=BASE, timeout=30)
        self.token = None
        self.ws = None

    def h(self, extra=None):
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.ws:
            h["X-Workspace-Id"] = self.ws
        h.update(extra or {})
        return h

    def req(self, method, path, expect=(200, 201, 204), what=None, **kw):
        headers = self.h(kw.pop("headers", None))
        try:
            r = self.c.request(method, path, headers=headers, **kw)
        except Exception as ex:  # noqa: BLE001
            problems.append(f"BAD EXC {self.name} {method} {path}: {ex}")
            return None
        exp = expect if isinstance(expect, (tuple, list, set)) else (expect,)
        ok = r.status_code in exp and r.status_code < 500
        rec(ok, f"[{self.name}] {method} {path}", r, what or "")
        return r


def j(r):
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return None


now = datetime.now(timezone.utc)
iso = lambda d: d.isoformat()  # noqa: E731
suffix = uuid.uuid4().hex[:8]

A, B = Client("A"), Client("B")
for u in (A, B):
    email = f"e2e-{u.name.lower()}-{suffix}@example.com"
    u.req("POST", "/auth/register", (201,), json={"email": email, "password": "Passw0rd!x", "full_name": f"User {u.name}"})
    r = u.req("POST", "/auth/login", (200,), json={"email": email, "password": "Passw0rd!x"})
    u.token = (j(r) or {}).get("access_token")
    u.req("GET", "/auth/me", (200,))
    r = u.req("GET", "/workspaces", (200,))
    u.ws = ((j(r) or [{}])[0]).get("id")

A.req("POST", "/auth/register", (409,), what="duplicate email", json={"email": f"e2e-a-{suffix}@example.com", "password": "Passw0rd!x", "full_name": "dup"})
anon = Client("anon")
anon.req("GET", "/tasks", (401,), what="no token")

# ---------------- tasks
r = A.req("POST", "/tasks", (201,), json={"title": "E2E task", "priority": "high", "due_at": iso(now + timedelta(hours=2))})
task = j(r) or {}
tid, ver = task.get("id"), task.get("version")
A.req("GET", "/tasks", (200,))
A.req("GET", f"/tasks/{tid}", (200,))
r = A.req("PATCH", f"/tasks/{tid}", (200,), json={"priority": "low"}, headers={"If-Match": f'"{ver}"'})
A.req("PATCH", f"/tasks/{tid}", (412, 409), what="stale etag", json={"priority": "high"}, headers={"If-Match": f'"{ver}"'})
A.req("PATCH", f"/tasks/{tid}", (428,), what="no If-Match", json={"priority": "high"})
A.req("POST", f"/tasks/{tid}/complete", (200,))
r = A.req("GET", f"/tasks/{tid}", (200,))
if (j(r) or {}).get("status") != "done":
    rec(False, "task status persisted as done", r)
A.req("GET", "/kanban/", (200,))
A.req("POST", "/tasks", (422,), what="empty title", json={"title": ""})
r2 = A.req("POST", "/tasks", (201,), json={"title": "to delete"})
t2 = j(r2) or {}

# attachments
r = A.req("POST", f"/tasks/{tid}/attachments", (200, 201), files={"file": ("note.txt", io.BytesIO(b"hello e2e"), "text/plain")})
att = j(r) or {}
att_id = att.get("id") if isinstance(att, dict) else None
if att_id:
    r = A.req("GET", f"/attachments/{att_id}/download", (200,))
    if r is not None and r.content != b"hello e2e":
        rec(False, "attachment content round-trip", r)
A.req("GET", f"/tasks/{tid}/attachments", (200,))

# ---------------- projects / goals / milestones
r = A.req("POST", "/goals", (201,), json={"title": "E2E goal"})
gid = (j(r) or {}).get("id")
r = A.req("POST", "/projects", (201,), json={"name": "E2E project", "goal_id": gid})
pid = (j(r) or {}).get("id")
A.req("GET", "/projects", (200,))
A.req("GET", f"/projects/{pid}", (200,))
A.req("PATCH", f"/projects/{pid}", (200,), json={"description": "updated"})
r = A.req("POST", "/milestones", (201,), json={"title": "M1", "due_date": str(date.today() + timedelta(days=7)), "project_id": pid})
mid = (j(r) or {}).get("id")
A.req("GET", "/milestones", (200,))
A.req("GET", "/goals", (200,))

# ---------------- calendar
r = A.req("POST", "/calendar/events", (201,), json={"title": "E2E meeting", "starts_at": iso(now + timedelta(hours=3)), "ends_at": iso(now + timedelta(hours=4))})
eid = (j(r) or {}).get("id")
A.req("GET", "/calendar/events", (200,), params={"start": iso(now - timedelta(days=1)), "end": iso(now + timedelta(days=2))})
A.req("POST", "/calendar/time-blocks", (201,), json={"task_id": tid, "starts_at": iso(now + timedelta(hours=5)), "ends_at": iso(now + timedelta(hours=6)), "label": "Focus"})
A.req("GET", "/calendar/time-blocks", (200,))
A.req("GET", "/calendar/free-busy", (200,), params={"date": str(date.today())})
A.req("POST", "/calendar/events", (422, 400), what="ends before starts", json={"title": "bad", "starts_at": iso(now + timedelta(hours=4)), "ends_at": iso(now + timedelta(hours=3))})

# ---------------- finance
r = A.req("POST", "/finance/accounts", (201,), json={"name": "Наличные", "type": "cash", "currency": "UZS", "initial_balance_minor": 100_000_00})
acc = j(r) or {}
aid = acc.get("id")
r = A.req("POST", "/finance/categories", (201,), json={"name": "Такси", "type": "expense"})
cid = (j(r) or {}).get("id")
r = A.req("POST", "/finance/transactions", (201,), headers={"Idempotency-Key": f"e2e-{suffix}"}, json={"account_id": aid, "amount_minor": 45_000_00, "currency": "UZS", "transaction_type": "expense", "category_id": cid, "note": "такси"})
tx = j(r) or {}
r_dup = A.req("POST", "/finance/transactions", (200, 201), what="idempotent replay", headers={"Idempotency-Key": f"e2e-{suffix}"}, json={"account_id": aid, "amount_minor": 45_000_00, "currency": "UZS", "transaction_type": "expense", "category_id": cid})
r = A.req("GET", f"/finance/accounts/{aid}", (200,))
bal = (j(r) or {}).get("current_balance_minor")
if bal != 55_000_00:
    rec(False, f"balance after expense (+idempotent replay) expected 5500000, got {bal}", r)
A.req("POST", f"/finance/transactions/{tx.get('id')}/reverse", (201,))
r = A.req("GET", f"/finance/accounts/{aid}", (200,))
if (j(r) or {}).get("current_balance_minor") != 100_000_00:
    rec(False, "balance restored after reversal", r)
A.req("POST", f"/finance/transactions/{tx.get('id')}/reverse", (409, 400), what="double reversal")
A.req("POST", "/finance/transactions", (422,), what="negative amount", json={"account_id": aid, "amount_minor": -5, "currency": "UZS"})
A.req("GET", "/finance/transactions", (200,))
A.req("POST", "/finance/budgets", (201,), json={"name": "Месяц", "amount_minor": 1_500_000_00, "currency": "UZS"})
A.req("GET", "/finance/budgets", (200,))
A.req("POST", f"/finance/accounts/{aid}/reconcile", (200, 201), json={"actual_balance_minor": 99_000_00, "reason": "e2e reconcile"})

# ---------------- knowledge
r = A.req("POST", "/knowledge/notes", (201,), json={"title": "E2E note", "content_markdown": "# Hello\nPersonal OS e2e"})
nid = (j(r) or {}).get("id")
A.req("GET", "/knowledge/notes", (200,))
A.req("GET", f"/knowledge/notes/{nid}", (200,))
A.req("PATCH", f"/knowledge/notes/{nid}", (200,), json={"title": "E2E note 2"})
A.req("GET", "/knowledge/search", (200,), params={"q": "Hello"})

# ---------------- planner
r = A.req("POST", "/planner/habits", (201,), json={"title": "Зарядка"})
hid = (j(r) or {}).get("id")
A.req("POST", f"/planner/habits/{hid}/toggle", (200,), params={"target_date": str(date.today())})
r = A.req("GET", "/planner/habits", (200,))
if not any(h.get("id") == hid and h.get("is_completed_today") for h in (j(r) or [])):
    rec(False, "habit toggle persisted", r)
A.req("PUT", "/planner/journal", (200,), json={"entry_date": str(date.today()), "evening_reflection": "Хороший день"})
r = A.req("GET", "/planner/journal", (200,), params={"entry_date": str(date.today())})
if (j(r) or {}).get("evening_reflection") != "Хороший день":
    rec(False, "journal persisted", r)
r = A.req("POST", "/planner/reminders", (201,), json={"title": "E2E reminder", "remind_at": iso(now + timedelta(hours=1))})
rid = (j(r) or {}).get("id")
r = A.req("GET", "/planner/reminders", (200,))
if not any(x.get("id") == rid for x in (j(r) or [])):
    rec(False, "reminder persisted", r)
A.req("GET", "/planner/agenda", (200,))
A.req("POST", f"/planner/reminders/{rid}/dismiss", (204,))

# ---------------- dashboard / notifications / ai
A.req("GET", "/dashboard/today", (200,))
A.req("GET", "/dashboard/summary", (200,))
A.req("GET", "/notifications/", (200,))
A.req("GET", "/notifications/unread-count", (200,))
A.req("POST", "/ai/parse", (200,), json={"text": "45000 такси"})
A.req("GET", "/advisor/brief", (200,))
r = A.req("POST", "/ai/plans", (201,), json={"request": "Спланируй мой день"})
plan = j(r) or {}
if plan.get("plan_id") and plan.get("changes"):
    A.req("POST", f"/ai/plans/{plan['plan_id']}/apply", (200,))
A.req("POST", "/ai/consult", (200,), json={"message": "Что сделать сегодня?"})

# ---------------- integrations (no external creds)
A.req("GET", "/integrations/telegram/status", (200,))
A.req("POST", "/integrations/telegram/pairing-code", (409,), what="no bot connected")
A.req("GET", "/integrations/github/status", (200,))
A.req("GET", "/integrations/google/sync-status", (200,))


# ---------------- read-after-write persistence checks
def present(client, path, oid, key="id"):
    r = client.req("GET", path, (200,), what="readback")
    data = j(r)
    items = data.get("items") if isinstance(data, dict) and "items" in data else data
    if not isinstance(items, list) or not any(isinstance(x, dict) and x.get(key) == oid for x in items):
        rec(False, f"persisted: {oid} in {path}", r)

present(A, "/goals", gid)
present(A, "/projects", pid)
present(A, "/milestones", mid)
present(A, "/calendar/events", eid)
r = A.req("GET", "/calendar/time-blocks", (200,), what="readback")
if not (j(r) or []):
    rec(False, "persisted: time block", r)
r = A.req("GET", "/finance/budgets", (200,), what="readback")
if not (j(r) or []):
    rec(False, "persisted: budget", r)
r = A.req("GET", "/finance/categories", (200,), what="readback")
if not any(c.get("id") == cid for c in (j(r) or [])):
    rec(False, "persisted: category", r)

# ---------------- cross-tenant: B must not see/modify A's data
B.req("GET", f"/tasks/{tid}", (404, 403), what="IDOR read task")
B.req("PATCH", f"/tasks/{tid}", (404, 403, 428), what="IDOR patch task", json={"title": "pwned"}, headers={"If-Match": '"99"'})
B.req("POST", f"/tasks/{tid}/complete", (404, 403), what="IDOR complete task")
B.req("DELETE", f"/tasks/{t2.get('id')}", (404, 403), what="IDOR delete task")
B.req("GET", f"/projects/{pid}", (404, 403), what="IDOR read project")
B.req("PATCH", f"/projects/{pid}", (404, 403), what="IDOR patch project", json={"name": "pwned"})
B.req("DELETE", f"/projects/{pid}", (404, 403), what="IDOR delete project")
B.req("GET", f"/finance/accounts/{aid}", (404, 403), what="IDOR read account")
B.req("POST", "/finance/transactions", (404, 403, 422), what="IDOR spend from A's account", json={"account_id": aid, "amount_minor": 1, "currency": "UZS", "transaction_type": "expense"})
B.req("GET", f"/knowledge/notes/{nid}", (404, 403), what="IDOR read note")
B.req("DELETE", f"/knowledge/notes/{nid}", (404, 403), what="IDOR delete note")
B.req("POST", f"/planner/habits/{hid}/toggle", (404, 403), what="IDOR toggle habit")
B.req("POST", f"/planner/reminders/{rid}/dismiss", (404, 403), what="IDOR dismiss reminder")
if att_id:
    B.req("GET", f"/attachments/{att_id}/download", (404, 403), what="IDOR download attachment")
B.req("GET", "/tasks", (200,), what="B list tasks")
r = B.req("GET", "/tasks", (200,))
if any(t.get("id") == tid for t in ((j(r) or {}).get("items") or [])):
    rec(False, "B sees A's task in list", r)
B.req("GET", "/tasks", (403,), what="foreign X-Workspace-Id", headers={"X-Workspace-Id": A.ws})
r = B.req("GET", "/finance/transactions", (200,))
if any(x.get("account_id") == aid for x in (j(r) or [])):
    rec(False, "B sees A's transactions", r)

# ---------------- cleanup-ish deletes for A (must work)
A.req("DELETE", f"/tasks/{t2.get('id')}", (204,))
A.req("DELETE", f"/knowledge/notes/{nid}", (204,))
A.req("DELETE", f"/planner/habits/{hid}", (204,))
if att_id:
    A.req("DELETE", f"/attachments/{att_id}", (204,))
A.req("DELETE", f"/milestones/{mid}", (204,))
A.req("DELETE", f"/projects/{pid}", (204,))

# ---------------- gateway (static + proxy)
if GW:
    g = httpx.Client(base_url=GW, timeout=20)
    for path, exp in [("/", 200), ("/today/", 200), ("/notes/", 200), ("/tg/", 200), ("/api/v1/health", 200), ("/api/docs", 200), ("/nope-xyz/", 404)]:
        r = g.get(path)
        rec(r.status_code == exp, f"[gw] GET {path}", r)

print("\n".join(log))
print("\n==== PROBLEMS ====")
print("\n".join(problems) if problems else "none")
