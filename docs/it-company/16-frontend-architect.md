# 16. Frontend Architect

## 1. Структура страниц и маршрутизация (Next.js App Router)
- `/today` — Смарт-дашборд «Сегодня» (динамический фильтр `due_date <= today` или `scheduled_date <= today`, таймблоки, Quick Add).
- `/tasks` — Список задач и интерактивная Kanban-доска:
  - **Рабочие колонки (5):** `Inbox`, `Todo`, `Scheduled`, `In Progress`, `Waiting`.
  - **Завершенные:** список `Done` и `Cancelled`.
  - **Архив:** скрытое состояние `Archived`.
- `/finance` — Финансовый обзор (счета, журнал транзакций, модалка сверки `reconcile`, сторнирование `reverse`).
- `/projects` — Проекты с прогресс-барами и фильтром по жизненному циклу (`planning`, `active`, `on_hold`, `completed`, `archived`).
- `/settings/integrations` — Настройки интеграций (Google OAuth 2.0, Telegram Bot, GitHub).

## 2. Контракт управления состоянием и хуков (Logic Contract)
- `useTasks(options)`: `tasks`, `isLoading`, `createTask()`, `completeTask()`, `updateStatus()`.
- `useFinance()`: `accounts`, `transactions`, `reconcileAccount(id, actual, reason)`, `reverseTransaction(id, reason)`.
- `useQuickAdd()`: `parseInput(text)`, `confirmProposal(actionId)`, `rejectProposal(actionId)`.

## 3. Контракт визуальных компонентов (UI Component Contract)
- `ReconciliationModal(isOpen, account, onClose, onReconcile)`
- `KanbanBoard(columns, onMoveTask)`
- `QuickAddBar(onParsed, onConfirm)`
- `TodayTaskItem(task, onToggleComplete)`

---

STATUS: VERIFIED
TASK: Разработка архитектуры фронтенда и разделение контрактов Logic / UI
INPUT: docs/it-company/04-solution-architect.md, docs/it-company/12-backend-integration-engineer.md, docs/it-company/18-ui-designer.md
ACTIONS:
  - Определена структура страниц Next.js App Router.
  - Разделены контракты Logic (hooks/state) и UI компонентов.
CHANGED_FILES:
  - docs/it-company/16-frontend-architect.md
FINDINGS: none
FIXES: n/a
VALIDATION: Архитектура обеспечивает полную синхронизацию типов с OpenAPI бэкенда.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/16-frontend-architect.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Разделение хуков по доменам с поддержкой автоматической инвалидации кэша через TanStack Query.
HANDOFF: Контракты переданы Frontend Logic Developer (19) и UI Component Developer (20).
NEXT_AGENT: 19 Frontend Logic Developer
