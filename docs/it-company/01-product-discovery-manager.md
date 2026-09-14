# 01. Product Discovery Manager (Главный аналитик продукта)

## 1. Product Vision & Назначение
**Personal OS** — персональная операционная система и интеллектуальный ассистент для управления задачами, проектами, личными финансами, календарем и привычками. Объединяет строгую изоляцию данных (PostgreSQL Multi-tenant RLS), детерминированный неизменяемый финансовый журнал (Single Source of Truth) и проактивного ИИ-советника (AI Advisor & Quick Add) с многоуровневым контролем безопасности (Tool Gateway).

## 2. Product Requirements Document (PRD)

### 2.1. Модуль задач и проектов (Tasks & Projects)
- **8 канонических статусов**: inbox, todo, scheduled, in_progress, waiting, done, cancelled, archived.
- **Правило Today**: today — это динамический Smart View (scheduled_date <= today или due_date <= today при активном статусе todo/scheduled/in_progress/waiting), а не статус.
- **Канбан-доска**: колонки inbox, todo, in_progress, waiting, done.
- **Жизненный цикл проектов**: planning -> active -> on_hold -> completed -> archived.
- **Прогресс**: (done_tasks / total_tasks) * 100%. При 0 задач — прогресс 0%. В архивных проектах создание задач заблокировано.

### 2.2. Финансовый модуль (Finance & Ledger)
- **Канонические типы счетов**: checking (Uzcard/Humo/Visa/Mastercard), savings, credit_card, cash, investment, crypto.
- **Неизменяемый финансовый журнал**:
  - Прямое изменение балансов (PATCH /finance/accounts/{id} с balance_minor) строго запрещено.
  - Баланс счета всегда детерминированно равен сумме проведённых (posted) транзакций за вычетом сторнированных.
  - Корректировка остатка только через транзакцию сверки reconciliation / opening_balance_adjustment.
  - Удаление счетов с историей запрещено (только soft delete / archived).
- **Мультивалютность и Minor Units**:
  - Базовая валюта воркспейса по умолчанию: UZS (1 сум = 100 тийинов, множитель 100), USD/EUR = 100 центов.
  - Обычные транзакции — строго в валюте счета.
  - Межвалютные переводы фиксируют: source_amount, source_currency, target_amount, target_currency, exchange_rate, rate_source.
- **Сторнирование (Reversal)**:
  - Запрещено повторное сторно (HTTP 409 Conflict).
  - Запрещено сторнировать операцию reversal.
  - Поля аудита: reversal_for_transaction_id, reversal_reason, reversed_at, reversed_by_user_id.
  - Исключение сторно из аналитики чистых расходов.

### 2.3. ИИ-ассистент, Quick Add и Tool Gateway
- **6-уровневая матрица рисков**:
  - Tier 1 (Read) -> Автоматически.
  - Tier 2 (Draft/Preview) -> Генерация превью.
  - Tier 3 (Mutate/Move/Reschedule) -> Запрос подтверждения.
  - Tier 4 (Finance) -> Строгий Preview + явное подтверждение.
  - Tier 5 (Integration/Sync) -> Подтверждение с тайм-аутом.
  - Tier 6 (Destructive/Drop/Delete) -> Полная блокировка для автономного AI.
- **Жизненный цикл Action Proposals**:
  - Сохранение в ai_actions, TTL = 15 минут, idempotency_key, хэш сущности.
  - Единое подтверждение через Web UI модалку и Telegram Inline Keyboard.
- **Quick Add NLP**:
  - Confidence >= 0.75 (при < 0.75 — уточняющий диалог).
  - Валюта по умолчанию берется из воркспейса (UZS, хардкод RUB удаляется).
  - Парсинг сумм: 45к, 45k, 45 000, 45000 сум, 45 тыс.

### 2.4. Интеграции
- **Web UI Management**: Client ID, Secret, Telegram Token настраиваются и шифруются (AES-256-GCM) в веб-интерфейсе (/settings/integrations).
- **Telegram**: Проверка секретного токена вебхука, привязка chat_id к воркспейсу через deep-link (/start link_<token>).
- **Google Calendar**: Двусторонняя синхронизация, PKCE, delta tokens, 410 Gone recovery, etag loop prevention.

### 2.5. Архитектура, RLS и API
- **PostgreSQL Multi-tenant RLS**: SET LOCAL app.current_workspace_id = ... для всех транзакций, запросов и воркеров.
- **Ошибки**: RFC 9457 Problem Details.
- **WebSocket Envelope**: event_id, event_type, workspace_id, aggregate_id, occurred_at, version, payload + Heartbeat.
- **Иерархия истины (docs/source-of-truth.md)**: Миграции БД -> Сервисы логики -> OpenAPI -> PRD -> Frontend типы.

## 3. Решение по условным ролям
- 13–15 (ML/CV / AI): REQUIRED (AI Advisor & Quick Add NLP).
- 20a (Data Visualization): REQUIRED (Финансовые чарты, аналитика задач и времени).
- 26a (Accessibility Auditor): REQUIRED (WCAG 2.1 AA доступность UI).
- 31 (SRE): SKIPPED (SKIPPED_REASON: Self-hosted MVP со встроенными метриками Prometheus/healthcheck).

---

STATUS: VERIFIED
TASK: Product Discovery & Canonical PRD for Personal OS
INPUT: Codebase audit, user request, agreed solutions
ACTIONS:
  - Analyzed 18 architecture/product points.
  - Formulated canonical PRD and passed Confirmation Gate.
  - Defined conditions for conditional roles.
CHANGED_FILES:
  - docs/it-company/01-product-discovery-manager.md
FINDINGS: Resolved status discrepancies, ledger model, AI confirmation lifecycle.
FIXES: n/a
VALIDATION: Confirmation Gate explicitly approved by user (да давай).
EVIDENCE:
  - [Тип: log_output]
  - [Артефакт: User confirmation message in conversation]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS: 8 task statuses, immutable ledger without direct balance edits, UZS workspace default, AI risk gateway.
HANDOFF: Complete canonical PRD ready for Business Analyst.
NEXT_AGENT: 02 Business Analyst
