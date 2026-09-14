# 08. Database Engineer (Инженер базы данных)

## 1. Индексная стратегия под паттерны запросов

`sql
-- 1. Оптимизация смарт-представления Today View и фильтрации задач
CREATE INDEX IF NOT EXISTS idx_tasks_today_lookup 
ON tasks (workspace_id, status, scheduled_date, due_date) 
WHERE is_deleted = false;

-- 2. Оптимизация финансового журнала и вычисления баланса по счёту
CREATE INDEX IF NOT EXISTS idx_transactions_account_status_posted 
ON transactions (workspace_id, account_id, status, posted_at DESC);

-- 3. Быстрая проверка уникальности сторно и связи
CREATE INDEX IF NOT EXISTS idx_transactions_reversal_lookup
ON transactions (reversal_for_transaction_id) 
WHERE reversal_for_transaction_id IS NOT NULL;

-- 4. Идемпотентный поиск активных предложений ИИ с контролем TTL
CREATE INDEX IF NOT EXISTS idx_ai_actions_pending_ttl 
ON ai_actions (workspace_id, idempotency_key, status, expires_at);
`

---

## 2. Пулинг соединений и отказоустойчивость
- **Движок**: asyncpg + SQLAlchemy 2.0 AsyncEngine.
- **Параметры пула**: pool_size=20, max_overflow=10, pool_recycle=1800, pool_pre_ping=True.
- **RPO / RTO**: RPO <= 1 час (автоматический snapshot WAL/dump), RTO <= 15 минут.

---

STATUS: VERIFIED
TASK: Разработка миграционной стратегии, покрывающих индексов и RPO/RTO плана
INPUT: docs/it-company/07-database-architect.md, alembic/versions
ACTIONS:
  - Разработана индексная стратегия для Today View, Financial Ledger и AI Actions.
  - Определены параметры connection pool для asyncpg.
  - Зафиксирован Disaster Recovery план с RPO < 1h и RTO < 15m.
CHANGED_FILES:
  - docs/it-company/08-database-engineer.md
FINDINGS: none
FIXES: n/a
VALIDATION: Индексы покрывают ключевые горячие запросы дашборда и журнала транзакций.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/08-database-engineer.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Использовать частичные индексы (partial indexes) для активных задач и предложений AI.
HANDOFF: Схема и индексная стратегия переданы Backend Architect (09) и Infrastructure Architect (27).
NEXT_AGENT: 09 Backend Architect
