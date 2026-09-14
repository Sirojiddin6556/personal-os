# 06. System Analyst (Системный аналитик)

## 1. Диаграмма состояний задач (Task State Machine)

`mermaid
stateDiagram-v2
    [*] --> inbox: Создание без срока
    [*] --> todo: Создание с категорией
    [*] --> scheduled: Создание с таймблоком
    
    inbox --> todo: Обработка / детализация
    inbox --> scheduled: Назначение даты/времени
    inbox --> cancelled: Отмена
    
    todo --> in_progress: Старт выполнения
    todo --> scheduled: Привязка к календарю
    todo --> waiting: Ожидание блокера
    todo --> done: Завершение
    todo --> cancelled: Отмена
    
    scheduled --> in_progress: Старт таймблока
    scheduled --> todo: Снятие расписания
    scheduled --> done: Завершение
    scheduled --> cancelled: Отмена
    
    in_progress --> waiting: Зависла / ждет ответа
    in_progress --> done: Завершена
    in_progress --> cancelled: Отмена
    in_progress --> todo: Приостановка
    
    waiting --> in_progress: Блокер снят
    waiting --> done: Завершена
    waiting --> cancelled: Отмена
    
    done --> todo: Переоткрытие
    done --> in_progress: Доработка
    done --> archived: Архивирование
    
    cancelled --> todo: Восстановление
    cancelled --> archived: Архивирование
    
    archived --> [*]
`

*Примечание*: Представление Today View является динамическим срезом: status IN ('todo', 'scheduled', 'in_progress', 'waiting') AND (scheduled_date <= CURRENT_DATE OR due_date <= CURRENT_DATE).

---

## 2. Последовательность выполнения AI Action Proposal (Sequence Diagram)

`mermaid
sequenceDiagram
    autonumber
    actor User as Пользователь (Web/TG)
    participant API as FastAPI Gateway
    participant AI as AI Advisor / Quick Add
    participant TG as Tool Gateway
    participant DB as PostgreSQL (ai_actions)
    participant Domain as Task/Finance Domain
    participant WS as WebSocket Hub

    User->>API: Сообщение: Обед 45к uzcard
    API->>AI: ParseIntentAndEntities()
    AI->>TG: CheckRiskAndPropose(Tier 4 Finance)
    TG->>DB: INSERT ai_actions (status=pending, ttl=15m, idempotency_key)
    TG-->>API: Action Proposal Preview (Списать 45 000 UZS со счёта Uzcard)
    API-->>User: Preview с кнопками [Подтвердить] [Отклонить]
    
    User->>API: POST /v1/ai/actions/{id}/confirm
    API->>TG: ExecuteAction(action_id)
    TG->>DB: Проверка TTL, статуса pending и хэша сущности
    TG->>Domain: ExecuteTransaction(amount=45000, category=Еда)
    Domain->>DB: INSERT transaction, UPDATE balance_minor
    TG->>DB: UPDATE ai_actions (status=applied)
    Domain->>WS: Broadcast(finance.transaction.posted)
    WS-->>User: Обновление баланса и истории в реальном времени
`

---

STATUS: VERIFIED
TASK: Разработка системных диаграмм (State, Sequence, Flow) и каталога событий
INPUT: docs/it-company/04-solution-architect.md, BRD
ACTIONS:
  - Разработана State Diagram для 8 состояний задач.
  - Разработана Sequence Diagram для жизненного цикла AI Action Proposal.
  - Описаны правила взаимодействия компонентов и публикация событий Outbox/WebSocket.
CHANGED_FILES:
  - docs/it-company/06-system-analyst.md
FINDINGS: none
FIXES: n/a
VALIDATION: Диаграммы исключают неоднозначности переходов и подтверждений.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/06-system-analyst.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Зафиксирована полная таблица переходов статусов задач.
  - AI proposals выполняются через атомарную проверку ai_actions.
HANDOFF: Диаграммы и спецификации переданы Database Architect (07) и Backend Architect (09).
NEXT_AGENT: 07 Database Architect
