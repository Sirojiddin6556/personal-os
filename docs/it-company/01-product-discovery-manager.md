# 01 — Product Discovery Manager

STATUS: VERIFIED
TASK: Провести Product Discovery для Personal OS — умного ежедневника / персональной операционной системы

---

## DECISIONS

### Условные роли
- **ML/CV блок (13–15)**: SKIPPED — SKIPPED_REASON: продукт не содержит собственных ML/CV моделей; AI используется через внешний LLM API, не требует отдельного ML Serving слоя
- **Data Visualization Engineer (20a)**: REQUIRED — продукт содержит Dashboard (Today, Finance, Analytics, Activity), нужны графики и чарты
- **Accessibility Auditor (26a)**: REQUIRED — публичный продукт с широкой аудиторией
- **SRE (31)**: SKIPPED — SKIPPED_REASON: MVP, нет production-нагрузки; добавить после первого production-релиза

---

## Product Vision

**Personal OS** — персональная операционная система для управления временем, задачами, финансами и знаниями с единым доменным ядром и AI-советником.

> Ключевой принцип: Telegram, Web, Gmail или Slack не создают собственные сущности — они лишь передают команды в одно ядро. Dashboard, Kanban и Calendar — разные представления одних и тех же данных.

---

## Пользователи и контексты

| Сегмент | Ключевые потребности |
|---|---|
| Knowledge Worker | Планирование дня, связь задач с календарём |
| Indie Hacker / Фрилансер | Трекинг расходов, дедлайны, Telegram-захват |
| Студент / Learner | Kanban, привычки, цели |

---

## MVP Scope (заморожен)

**Входит в MVP:**
- Authentication (OIDC/OAuth, MFA)
- Workspace / User Preferences
- Dashboard / Today (агрегация, не отдельное хранилище)
- Inbox / Quick Add (<=3 действия)
- Tasks + Subtasks + Priorities + Deadlines + Recurring (basic)
- Kanban (view над Task.status, не отдельная card-таблица)
- Projects
- Calendar + Time Blocks
- Google Calendar two-way sync
- Finance: Accounts, Income/Expense, Categories, Budgets
- Activity Timeline
- Notification Engine (Push/Telegram/WebSocket)
- Telegram Bot
- PWA basics
- Morning Brief (расчётный продукт + AI-комментарий)
- AI Capture + AI Schedule Preview
- Basic Notes + RAG
- Audit + Backups + Monitoring

**Исключено из MVP:**
- native iOS/Android, team collaboration, advanced accounting, bank API
- Gmail, Outlook, Slack, WhatsApp, Discord, SMS
- complex automation, microservices, Kubernetes

---

## Технологический стек (зафиксирован)

| Слой | Технология |
|---|---|
| Web/PWA | Next.js 14+ + TypeScript + React 18 |
| UI | Tailwind CSS + shadcn/ui |
| Client state | TanStack Query + Zustand |
| Backend | Python 3.12 + FastAPI |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Primary DB | PostgreSQL 16 + pgvector |
| Cache/Jobs | Redis 7 + Celery |
| Observability | OpenTelemetry + Prometheus + Grafana + Sentry |
| CI/CD | GitHub Actions |
| Deployment MVP | Docker Compose + managed PostgreSQL |

---

## Roadmap

| Фаза | Спринты | Exit gate |
|---|---|---|
| Product & Architecture | S0 | Architecture baseline approved |
| Platform Foundation | S1-S2 | Secure login, tenant isolation, deploy, backup |
| Productivity Core | S3-S5 | Task workflow E2E |
| Calendar & Google | S6-S8 | Two-way sync + replay tests |
| Finance & Activity | S9-S10 | Ledger/budget invariants |
| Notifications & Telegram | S11-S13 | Chat capture + reminder E2E |
| AI Advisor V1 | S14-S16 | Safe preview/apply, eval suite |
| Extended Integrations | S17-S19 | Gmail, Outlook, Slack, Discord |
| WhatsApp/SMS | S20-S21 | Provider/policy gate |
| Production Hardening | S22-S24 | Launch readiness review |

---

## HANDOFF
Следующий агент: 02-business-analyst
Передать: Product Vision, UC Matrix, MVP Scope (заморожен), Технологический стек, решения по условным ролям

## CHANGED_FILES
- docs/it-company/01-product-discovery-manager.md

## NEXT_AGENT: 02-business-analyst
