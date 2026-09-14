# 09. Backend Architect (Архитектор бэкенда)

## 1. Контракт сервисного слоя (Domain / Service Layer Contract)

### 1.1. Tasks Domain Service (src.domains.tasks.service)
`python
async def create_task(session: AsyncSession, workspace_id: UUID, payload: TaskCreateDTO) -> Task: ...
async def update_task(session: AsyncSession, workspace_id: UUID, task_id: UUID, payload: TaskUpdateDTO, expected_version: Optional[int] = None) -> Task: ...
async def complete_task(session: AsyncSession, workspace_id: UUID, task_id: UUID) -> Task: ...
async def list_tasks(session: AsyncSession, workspace_id: UUID, filter_today: bool = False, status: Optional[str] = None) -> List[Task]: ...
`

### 1.2. Finance Ledger Service (src.domains.finance.service)
`python
async def post_transaction(session: AsyncSession, workspace_id: UUID, payload: TransactionCreateDTO) -> Transaction:
    "Создает транзакцию и атомарно обновляет агрегированный баланс счета."
    ...

async def reconcile_account(session: AsyncSession, workspace_id: UUID, account_id: UUID, actual_balance_minor: int, reason: str) -> Transaction:
    "Создает транзакцию сверки (reconciliation) на разницу между текущим и фактическим балансом."
    ...

async def reverse_transaction(session: AsyncSession, workspace_id: UUID, transaction_id: UUID, reason: str, user_id: UUID) -> Transaction:
    "Сторнирует транзакцию, создает компенсирующую проводку. Блокирует повторное сторно."
    ...

async def transfer_funds(session: AsyncSession, workspace_id: UUID, payload: TransferCreateDTO) -> Tuple[Transaction, Transaction]:
    "Межвалютный перевод с фиксацией валют и курса конвертации."
    ...
`

### 1.3. AI Tool Gateway Service (src.domains.ai_advisor.tool_gateway)
`python
async def propose_action(session: AsyncSession, workspace_id: UUID, user_id: UUID, tool_name: str, payload: dict, risk_tier: int) -> AIAction:
    "Создает Action Proposal со статусом pending, TTL 15m и хэшем сущности."
    ...

async def confirm_action(session: AsyncSession, workspace_id: UUID, action_id: UUID, idempotency_key: str) -> dict:
    "Идемпотентно применяет подтвержденное действие, вызывая соответствующий доменный сервис."
    ...
`

---

## 2. HTTP API Маршруты и контракт RFC 9457

- POST /v1/tasks/{id}/complete — явное завершение задачи.
- POST /v1/finance/accounts/{id}/reconcile — сверка баланса счёта (прямой PATCH баланса отключён).
- POST /v1/finance/transactions/{id}/reverse — сторнирование транзакции.
- POST /v1/ai/quick-add — NLP парсинг и маршрутизация намерения (базовая валюта UZS).
- POST /v1/ai/actions/{id}/confirm — подтверждение действия ИИ.

---

STATUS: VERIFIED
TASK: Проектирование сервисного и API контрактов Backend
INPUT: docs/it-company/04-solution-architect.md, docs/it-company/05-security-architect.md, docs/it-company/08-database-engineer.md
ACTIONS:
  - Сформирован чистый сервисный контракт Domain Layer без привязки к HTTP.
  - Сформирован HTTP контракт с удалением прямого редактирования балансов и добавлением reconcile/reverse.
  - Определен контракт Tool Gateway с контролем рисков.
CHANGED_FILES:
  - docs/it-company/09-backend-architect.md
FINDINGS: none
FIXES: n/a
VALIDATION: Контракты исключают финансовые аномалии и обеспечивают строгую идемпотентность.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/09-backend-architect.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Сервисный слой полностью инкапсулирует вычисление балансов и outbox события.
HANDOFF: Контракты переданы Backend Business Logic Developer (10), Backend API Developer (11) и Frontend Architect (16).
NEXT_AGENT: 10 Backend Business Logic Developer
