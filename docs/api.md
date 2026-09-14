# Спецификация REST & WebSocket API v1

## 1. Общие принципы

### Аутентификация и контекст тенанта
- **Заголовок авторизации:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Контекст рабочего пространства:** `X-Workspace-Id: <UUID>`
- **Идемпотентность мутирующих запросов:** `Idempotency-Key: <UUID>` (поддерживается для `POST /v1/tasks`, `POST /v1/finance/transactions`)
- **Оптимистичная блокировка (RFC 9110 / RFC 6585):** Строгий сильный ETag `If-Match: "<version>"` (для мутирующих запросов с контролем версий, например `PATCH /v1/tasks/{task_id}`).
  > [!NOTE]
  > **Проектная политика Personal OS:** В рамках архитектуры Personal OS используется монотонная целочисленная версия сущности в кавычках (`"1"`, `"2"`). Хотя RFC 9110 допускает произвольные opaque entity-tags и weak tags, сервер Personal OS намеренно отклоняет слабые теги (`W/`) и wildcard (`*`) со статусом `400 Bad Request` (`INVALID_ETAG`) для гарантии строгой консистентности данных между distributed клиентами.
  - **428 Precondition Required:** Заголовок `If-Match` отсутствует в запросе (`code: "PRECONDITION_REQUIRED"`, `required_header: "If-Match"`).
  - **400 Bad Request:** Заголовок `If-Match` имеет невалидный формат (слабый ETag `W/...`, wildcard `*`, не числовое значение) (`code: "INVALID_ETAG"`).
  - **412 Precondition Failed:** Версия в `If-Match` валидна, но устарела / не совпадает с актуальной версией сущности (`code: "STALE_VERSION"`, возвращает `provided_version` и `current_version`).
  - **409 Conflict:** Нарушение бизнес-правил / инвариантов домена (`code: "RESOURCE_CONFLICT"`).
  - **422 Unprocessable Content:** Ошибка валидации структуры тела запроса (JSON schema / Pydantic validation).

### Формат ошибок (RFC 9457 Problem Details)
Все ошибки API возвращаются в едином стандартизированном JSON-формате (`Content-Type: application/problem+json`):
```json
{
  "type": "https://api.personal-os.local/errors/conflict",
  "title": "Conflict",
  "status": 409,
  "detail": "Cannot reverse a reversal transaction.",
  "instance": "/v1/finance/transactions/018f.../reverse"
}
```

---

## 2. Каталог эндпоинтов

### 2.1. Tasks API (`/v1/tasks`)
- `GET /v1/tasks` — Список задач с фильтрацией (`status`, `priority`, `project_id`, `today=true`), поиском (`q`), сортировкой и курсорной пагинацией (`cursor`, `limit`).
- `POST /v1/tasks` — Создание задачи.
- `GET /v1/tasks/{task_id}` — Получение задачи по идентификатору.
- `PATCH /v1/tasks/{task_id}` — Обновление полей задачи с контролем версии (`If-Match`).
- `POST /v1/tasks/{task_id}/complete` — Атомарный перевод задачи в статус `done` с фиксацией `completed_at`.
- `DELETE /v1/tasks/{task_id}` — Мягкое удаление задачи (`is_deleted = true`).
- `GET /v1/kanban/` — Получение доски Канбан со сгруппированными по 5 колонкам задачами.

### 2.2. Finance API (`/v1/finance`)
- `GET /v1/finance/accounts` — Список активных счетов и балансов в минорных единицах (`balance_minor`).
- `POST /v1/finance/accounts` — Создание нового счета (`name`, `currency`, `type`).
- `GET /v1/finance/accounts/{account_id}` — Получение счета по идентификатору.
- `PATCH /v1/finance/accounts/{account_id}` — Обновление названия, типа или статуса архивации (прямое изменение `balance_minor` запрещено).
- `DELETE /v1/finance/accounts/{account_id}` — Удаление пустого счета или архивация счета с транзакциями.
- `POST /v1/finance/accounts/{account_id}/reconcile` — Сверка баланса счета с созданием корректирующей транзакции `reconciliation`.
- `GET /v1/finance/transactions` — Список транзакций (`account_id`, `category_id`, `type`, `status`, `from_date`, `to_date`).
- `POST /v1/finance/transactions` — Проведение транзакции (`income`, `expense`, `transfer`).
- `PATCH /v1/finance/transactions/{transaction_id}` — Обновление описания или категории транзакции.
- `POST /v1/finance/transactions/{transaction_id}/reverse` — Сторнирование транзакции с восстановлением баланса счета.
- `GET /v1/finance/categories` / `POST /v1/finance/categories` — Управление категориями расходов и доходов.
- `GET /v1/finance/budgets` / `POST /v1/finance/budgets` — Месячные бюджеты по категориям (`YYYY-MM`).

### 2.3. Projects, Strategic Goals & Milestones (`/v1/projects`, `/v1/goals`, `/v1/milestones`)
- `GET /v1/projects` / `POST /v1/projects` — Список и создание проектов со статусами: `planning`, `active`, `on_hold`, `completed`, `archived`.
- `GET /v1/projects/{project_id}` / `PATCH /v1/projects/{project_id}` / `DELETE /v1/projects/{project_id}` — Управление проектом.
- `GET /v1/goals` / `POST /v1/goals` — Долгосрочные стратегические цели (`category`, `target_date`, `progress_percentage`, `status`).
- `GET /v1/goals/{goal_id}` / `PATCH /v1/goals/{goal_id}` / `DELETE /v1/goals/{goal_id}` — Управление целью.
- `GET /v1/milestones` / `POST /v1/milestones` — Ключевые вехи и дедлайны проектов и целей.
- `GET /v1/milestones/{milestone_id}` / `PATCH /v1/milestones/{milestone_id}` / `DELETE /v1/milestones/{milestone_id}` — Управление вехой.

### 2.4. Knowledge & Notes (`/v1/knowledge`)
- `GET /v1/knowledge/notes` / `POST /v1/knowledge/notes` — Управление Markdown-заметками.
- `GET /v1/knowledge/notes/{note_id}` / `PATCH /v1/knowledge/notes/{note_id}` / `DELETE /v1/knowledge/notes/{note_id}` — Просмотр, обновление и удаление заметки.
- `GET /v1/knowledge/search?q=...&limit=10` — Семантический векторный поиск по базе знаний (HNSW pgvector).

### 2.5. Planner, Habits & Calendar (`/v1/planner`, `/v1/calendar`)
- `GET /v1/planner/agenda` — Почасовая сетка дня (00:00 — 23:00) с событиями и тайм-блоками.
- `GET /v1/planner/habits` / `POST /v1/planner/habits` — Трекер ежедневных привычек.
- `POST /v1/planner/habits/{habit_id}/toggle` — Отметка выполнения привычки за текущую дату (`streak_days`).
- `DELETE /v1/planner/habits/{habit_id}` — Удаление привычки.
- `GET /v1/planner/journal` / `PUT /v1/planner/journal` — Просмотр и сохранение ежедневного дневника/рефлексии.
- `GET /v1/planner/reminders` / `POST /v1/planner/reminders` / `POST /v1/planner/reminders/{reminder_id}/dismiss` — Быстрые напоминания.
- `POST /v1/calendar/events` — Создание события календаря.
- `POST /v1/calendar/time-blocks` — Создание временного блока для задачи.

### 2.6. AI Advisor & Tool Gateway (`/v1/advisor`, `/v1/ai`)
- `POST /v1/advisor/parse` (alias `/v1/ai/parse`) — Парсинг свободного ввода на естественном языке (Quick Add).
- `POST /v1/advisor/plans` (alias `/v1/ai/plans`) — Формирование плана оптимизации расписания (Preview diff).
- `POST /v1/advisor/plans/{plan_id}/apply` (alias `/v1/ai/plans/{plan_id}/apply`) — Применение подтвержденного плана через Tool Gateway.
- `POST /v1/advisor/brief` — Генерация утренней сводки и рекомендаций.
- `POST /v1/advisor/rag-qa` — Интеллектуальный ответ на вопросы по базе знаний.
- `POST /v1/advisor/search-notes` — Векторный поиск заметок для AI-ассистента.
- `POST /v1/ai/actions/{action_id}/confirm` / `POST /v1/ai/actions/{action_id}/undo` — Интерактивное подтверждение и откат действий.
- `POST /v1/ai/consult` — Консультация с AI-ассистентом.

### 2.7. Integrations API (`/v1/integrations`)
- **Telegram Bot:**
  - `POST /v1/integrations/telegram/connect` — Подключение бота (валидация токена через Telegram `getMe` и сохранение).
  - `GET /v1/integrations/telegram/status` — Проверка статуса и имени подключенного бота.
  - `DELETE /v1/integrations/telegram` — Отключение Telegram-бота.
  - `POST /v1/webhooks/telegram/{webhook_id}` (alias `/webhooks/telegram/{webhook_id}`) — Вебхук входящих апдейтов Telegram.
- **Google Calendar:**
  - `POST /v1/integrations/google/configure` (alias `POST /v1/integrations/google/config`) — Сохранение Client ID и Client Secret из формы UI.
  - `GET /v1/integrations/google/config` — Проверка статуса и получение redirect_uri.
  - `GET /v1/integrations/google/authorize` (alias `/v1/integrations/google/auth-url`) — Генерация OAuth URL с PKCE.
  - `GET /v1/integrations/google/callback` — Обмен кода на токены.
  - `POST /v1/integrations/google/sync` — Запуск инкрементальной синхронизации.
  - `DELETE /v1/integrations/google/disconnect` — Отключение интеграции и отзыв токенов.
  - `POST /v1/integrations/google/webhook` — Прием push-уведомлений Google Calendar.
- **GitHub Integration:**
  - `GET /v1/integrations/github/status` / `POST /v1/integrations/github/connect` — Статус и подключение токена GitHub.
  - `GET /v1/integrations/github/repos` / `POST /v1/integrations/github/import` — Список и импорт репозиториев.
  - `GET /v1/integrations/github/projects/{project_id}/commits` — Коммиты проекта.
  - `GET /v1/integrations/github/projects/{project_id}/contents` / `GET /v1/integrations/github/projects/{project_id}/file` — Файлы репозитория.
  - `POST /v1/integrations/github/projects/{project_id}/commit` — Создание коммита.
  - `POST /v1/integrations/github/projects/{project_id}/sync-issues` — Синхронизация issues в задачи.

### 2.8. System & Health API (`/v1/health`)
- `GET /v1/health` (alias `GET /health`, `GET /v1/health/live`) — Liveness проверка работоспособности HTTP-процесса API.
- `GET /v1/health/ready` — Readiness проверка готовности ключевых зависимостей (PostgreSQL подключение, ключи AES-256-GCM).

---


## 3. Real-time WebSocket API (`/v1/ws`)

### Подключение
- **URL:** `ws://localhost:8000/v1/ws?token=<JWT_ACCESS_TOKEN>`
- **Heartbeat:** Пинг-понг каждые 30 секунд (`{"type": "ping"}` $\rightarrow$ `{"type": "pong"}`).

### Формат сообщений
```json
{
  "event": "finance.transaction.posted",
  "workspace_id": "d5f9ec5c-ad1a-419a-b5d6-80e9fba930d2",
  "payload": {
    "account_id": "018f3a5b-...",
    "transaction_id": "018f3a6c-...",
    "balance_minor": 15000000,
    "currency": "UZS"
  },
  "timestamp": "2026-09-14T10:30:00Z"
}
```

### Поддерживаемые события:
- `task.created`, `task.updated`, `task.completed`, `task.deleted`
- `finance.account_updated`, `finance.transaction.posted`, `finance.reconciled`
- `calendar.synced`, `calendar.event_changed`
- `ai.plan_ready`, `ai.action_required`

