---
name: "Personal OS Orchestrator"
description: "Mandatory orchestration skill for AI coding agents (Claude Code, Codex, Antigravity, OpenCode). Forces agents to register tasks, manage Kanban lifecycles, log progress, and track projects via the Personal OS API (http://localhost:8008/v1) instead of pushing raw changes to GitHub directly."
---

# Personal OS Orchestrator & Task Hub

## What This Skill Does

This skill enforces a strict **Personal OS-First Development Workflow**. AI agents are prohibited from making uncoordinated edits or pushing commits directly to GitHub without first orchestrating their work through the local **Personal OS** domain engine.

Whenever an AI agent is asked to fix a bug, implement a feature, refactor code, or plan an architecture, it must:
1. **Discover or Create** the task in Personal OS (`/v1/tasks`).
2. **Transition Status** on the Kanban board to `in_progress` using optimistic concurrency (`If-Match: "<version>"`).
3. **Execute and Verify** code locally (running tests and typechecks).
4. **Log Progress** and store architectural context in Personal OS Knowledge base (`/v1/knowledge/notes`).
5. **Mark Done & Sync** task status to `done`, optionally attaching GitHub commit hashes or PR metadata.

---

## Configuration & Connection

| Parameter | Default Value | Notes |
| :--- | :--- | :--- |
| **API Base URL** | `http://localhost:8008/v1` | Local Personal OS FastAPI Service |
| **Web Dashboard** | `http://localhost:3000` | Kanban Board (`/tasks`), Dashboard (`/today`) |
| **Auth Header** | `Authorization: Bearer <jwt_token>` | Use active workspace JWT or dev token |
| **Concurrency Header** | `If-Match: "<version>"` | **Required** for all `PATCH` / `PUT` mutations |

---

## 5-Step Agent Workflow Protocol

```
1. QUERY / CREATE TASK  ──►  2. MOVE TO IN_PROGRESS  ──►  3. DEVELOP & TEST  ──►  4. LOG DECISION  ──►  5. COMPLETE TASK
   (POST /v1/tasks)            (PATCH If-Match: "1")         (Unit/E2E tests)      (POST /v1/notes)      (PATCH status: done)
```

### Step 1: Query or Create Task in Personal OS
Before modifying any files in the workspace:
- Check existing open tasks:
  ```bash
  curl -s -X GET "http://localhost:8008/v1/tasks?status=todo&limit=10" \
    -H "Authorization: Bearer $PERSONAL_OS_TOKEN"
  ```
- Or register a new task:
  ```bash
  curl -s -X POST "http://localhost:8008/v1/tasks" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $PERSONAL_OS_TOKEN" \
    -d '{
      "title": "Implement JWT Refresh Token rotation",
      "description": "Add secure token rotation to prevent session hijacking.",
      "priority": "high",
      "status": "todo"
    }'
  ```

---

### Step 2: Transition Task to `in_progress`
When starting active coding work:
- Update status with the required `If-Match` header:
  ```bash
  curl -s -X PATCH "http://localhost:8008/v1/tasks/<TASK_UUID>" \
    -H "Content-Type: application/json" \
    -H "If-Match: \"1\"" \
    -H "Authorization: Bearer $PERSONAL_OS_TOKEN" \
    -d '{
      "status": "in_progress"
    }'
  ```

---

### Step 3: Implement Code & Run Automated Tests
Execute work inside the repository according to project guidelines:
- Run backend unit and integration tests:
  ```bash
  python -m pytest apps/api/tests
  ```
- Run frontend unit and typechecks:
  ```bash
  npm --prefix apps/web test
  npx tsc --noEmit
  ```

---

### Step 4: Record Architectural Decisions (Knowledge Base)
If your task introduces architectural changes, schema migrations, or new domain policies, save a note in Personal OS Knowledge base:
```bash
curl -s -X POST "http://localhost:8008/v1/knowledge/notes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PERSONAL_OS_TOKEN" \
  -d '{
    "title": "ADR: JWT Refresh Token Rotation Policy",
    "content": "Implemented rotating refresh tokens with 7-day TTL and Redis revocation list.",
    "tags": ["security", "auth", "backend"]
  }'
```

---

### Step 5: Mark Task Done & Attach GitHub Reference
After all tests pass and code is ready for commit:
- Fetch current version if mutated:
  ```bash
  TASK=$(curl -s "http://localhost:8008/v1/tasks/<TASK_UUID>" -H "Authorization: Bearer $PERSONAL_OS_TOKEN")
  VERSION=$(echo $TASK | jq -r '.version')
  ```
- Update status to `done`:
  ```bash
  curl -s -X PATCH "http://localhost:8008/v1/tasks/<TASK_UUID>" \
    -H "Content-Type: application/json" \
    -H "If-Match: \"$VERSION\"" \
    -H "Authorization: Bearer $PERSONAL_OS_TOKEN" \
    -d '{
      "status": "done"
    }'
  ```

---

## Domain Status & Kanban Mapping Reference

| Kanban Column | Supported Domain Statuses | Typical Agent Usage |
| :--- | :--- | :--- |
| **Inbox** | `inbox`, `draft` | Quick captured ideas, unprocessed user requests |
| **Todo** | `todo` | Approved work items ready for agent pickup |
| **Scheduled** | `scheduled` | Tasks deferred to a specific calendar date/time |
| **In Progress** | `in_progress`, `review` | Active code changes, undergoing test/review |
| **Waiting** | `waiting`, `blocked`, `delegated` | Blocked by external dependency or awaiting user input |
| *(Done Archive)* | `done`, `archived`, `cancelled` | Completed or closed work |

---

## Concurrency & Header Rules
- Always use single-quoted / double-quoted integer versions: `If-Match: "1"`.
- Do not use wildcard `*` or weak tags `W/`.
