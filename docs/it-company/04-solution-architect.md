# 04. Solution Architect (Архитектор системы)

## 1. Архитектурный стиль и паттерны
- **Архитектурный паттерн**: Модульный монолит с разделением по доменам (Domain-Driven Design).
- **Слои**:
  - **API Layer** (FastAPI Routers): Обработка HTTP/WebSocket, валидация входных данных через Pydantic v2, преобразование исключений в RFC 9457.
  - **Domain Service Layer**: Бизнес-инварианты, управление транзакциями, outbox-события, расчет балансов, Tool Gateway.
  - **Data Access & Storage Layer**: SQLAlchemy 2.0 AsyncSession, PostgreSQL с Row Level Security (RLS) на уровне каждого воркспейса.
  - **Frontend UI Layer**: Next.js App Router, типизированные хуки взаимодействия с API, оптимистичные обновления, адаптивный UI.

## 2. Диаграмма взаимодействия компонентов (Mermaid)

`mermaid
graph TD
  User[Пользователь (Web / Telegram)] --> API[FastAPI Gateway (Port 8008)]
  API --> Auth[Auth & Tenant Context Middleware]
  Auth --> TG[AI Tool Gateway & Policy Engine]
  Auth --> TasksDomain[Tasks Domain Service]
  Auth --> FinanceDomain[Finance Ledger Service]
  Auth --> Integrations[Integrations Service (AES-256-GCM)]
  
  FinanceDomain --> DB[(PostgreSQL 16 (Multi-tenant RLS))]
  TasksDomain --> DB
  TG --> DB
  Integrations --> DB
  
  FinanceDomain --> Outbox[Outbox Events]
  Outbox --> WS[WebSocket Event Broadcaster]
  WS --> Frontend[Next.js Web App (Port 3000)]
`

## 3. Ключевые архитектурные решения (ADR)
- **ADR-01: Неизменяемый финансовый журнал**: Запрет мутации баланса через REST PATCH; все изменения только через создание транзакций (включая reconciliation).
- **ADR-02: Мультитенантность через PostgreSQL RLS**: Установка контекста сессии SET LOCAL app.current_workspace_id на уровне middleware и background-воркеров.
- **ADR-03: Единый формат ошибок RFC 9457 Problem Details**: Стандартизированный JSON-ответ для всех классов ошибок.
- **ADR-04: Безопасность AI Tool Gateway**: 6 уровней рисков с гарантированным тайм-аутом (15 мин) и идемпотентностью предложений.

---

STATUS: VERIFIED
TASK: Разработка системной архитектуры и ADR для Personal OS
INPUT: docs/it-company/01-product-discovery-manager.md, docs/it-company/02-business-analyst.md, docs/it-company/03-product-manager.md
ACTIONS:
  - Определен модульный монолит DDD с четкими границами доменов.
  - Зафиксированы ADR по неизменяемому ledger, RLS, RFC 9457 и Tool Gateway.
  - Составлена C4/компонентная диаграмма взаимодействия.
CHANGED_FILES:
  - docs/it-company/04-solution-architect.md
FINDINGS: none
FIXES: n/a
VALIDATION: Архитектурные решения полностью соответствуют требованиям безопасности и бизнес-инвариантам.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/04-solution-architect.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS: Модульный монолит на FastAPI + Next.js + PostgreSQL RLS с Outbox паттерном.
HANDOFF: Архитектурный документ готов для этапов 05 Security Architect, 06 System Analyst и 07 Database Architect.
NEXT_AGENT: 05 Security Architect
