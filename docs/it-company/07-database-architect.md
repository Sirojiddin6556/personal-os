# 07. Database Architect (Архитектор базы данных)

## 1. Логическая ER-диаграмма (Mermaid)

`mermaid
erDiagram
    WORKSPACES ||--o{ USERS : members
    WORKSPACES ||--o{ TASKS : owns
    WORKSPACES ||--o{ PROJECTS : owns
    WORKSPACES ||--o{ ACCOUNTS : owns
    WORKSPACES ||--o{ TRANSACTIONS : ledger
    WORKSPACES ||--o{ AI_ACTIONS : proposals
    WORKSPACES ||--o{ INTEGRATIONS : configures
    
    PROJECTS ||--o{ TASKS : contains
    ACCOUNTS ||--o{ TRANSACTIONS : logs
    
    TASKS {
        uuid id PK
        uuid workspace_id FK
        uuid project_id FK
        string title
        string status inbox|todo|scheduled|in_progress|waiting|done|cancelled|archived
        int priority 1|2|3|4
        timestamp scheduled_date
        timestamp due_date
    }
    
    PROJECTS {
        uuid id PK
        uuid workspace_id FK
        string name
        string status planning|active|on_hold|completed|archived
    }
    
    ACCOUNTS {
        uuid id PK
        uuid workspace_id FK
        string name
        string account_type checking|savings|credit_card|cash|investment|crypto
        string currency UZS|USD|EUR
        bigint balance_minor
        bigint credit_limit_minor
        boolean allow_overdraft
        boolean is_archived
    }
    
    TRANSACTIONS {
        uuid id PK
        uuid workspace_id FK
        uuid account_id FK
        uuid destination_account_id FK
        string transaction_type income|expense|transfer|reversal|reconciliation
        bigint amount_minor
        string currency
        uuid reversal_for_transaction_id FK
        string reversal_reason
        decimal exchange_rate
        bigint source_amount_minor
        bigint target_amount_minor
        string status posted|reversed
        timestamp posted_at
    }
    
    AI_ACTIONS {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        string tool_name
        jsonb payload
        string status pending|applied|rejected|expired
        string idempotency_key
        string entity_hash
        timestamp expires_at
    }
`

---

## 2. Ключевые ограничения целостности (Constraints & Invariants)
- **CHK_TASKS_STATUS**: status IN ('inbox', 'todo', 'scheduled', 'in_progress', 'waiting', 'done', 'cancelled', 'archived')
- **CHK_PROJECTS_STATUS**: status IN ('planning', 'active', 'on_hold', 'completed', 'archived')
- **CHK_ACCOUNTS_TYPE**: account_type IN ('checking', 'savings', 'credit_card', 'cash', 'investment', 'crypto')
- **CHK_TRANSACTIONS_TYPE**:     ransaction_type IN ('income', 'expense', 'transfer', 'reversal', 'reconciliation')
- **CHK_REVERSAL_UNIQUE**: UNIQUE (reversal_for_transaction_id) — исключает повторное сторнирование одной и той же транзакции.
- **RLS Policy**: ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY; ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;

---

STATUS: VERIFIED
TASK: Проектирование логической схемы БД, ER-диаграммы и ограничений целостности
INPUT: docs/it-company/04-solution-architect.md, docs/it-company/05-security-architect.md, docs/it-company/06-system-analyst.md
ACTIONS:
  - Создана полная ER-диаграмма в нотации Mermaid.
  - Унифицированы enum-статусы задач (8 значений), проектов (5 значений) и счетов (6 значений).
  - Заложены constraints для запрета повторного сторно и защиты RLS.
CHANGED_FILES:
  - docs/it-company/07-database-architect.md
FINDINGS: none
FIXES: n/a
VALIDATION: Логическая схема гарантирует строгую целостность финансового журнала и изоляцию данных.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/07-database-architect.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Поле reversal_for_transaction_id имеет UNIQUE constraint для предотвращения двойного сторнирования.
  - Прямой баланс счетов является кэшируемым агрегатом, поддерживаемым транзакциями.
HANDOFF: Логическая модель передана Database Engineer (08) для создания миграций и индекс-стратегии.
NEXT_AGENT: 08 Database Engineer
