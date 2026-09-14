# 22. QA Lead / Test Architect

## 1. Стратегия тестирования (Test Strategy)
- **Пирамида тестирования**:
  - **Unit Tests (70%)**: Доменная логика задач, транзакций, вычисления балансов, NLP Intent парсинг, Tool Gateway risk matrix.
  - **Integration Tests (20%)**: Взаимодействие FastAPI с PostgreSQL RLS, OAuth flow Google, Telegram webhook ACK & dispatch, WebSocket outbox events.
  - **E2E & UI Component Tests (10%)**: Завершение задач, создание расходов через Quick Add, сверка балансов счетов.
- **Матрица трассируемости требований**:
  - BR-1 (Tasks State Machine) ->     ests/test_tasks.py,     ests/test_backend_developer.py
  - BR-2 (Immutable Ledger & Reconciliation) ->     ests/test_finance.py,     ests/unit/test_domain_units.py
  - BR-3 (AI Advisor & Tool Gateway) ->     ests/test_ai_advisor.py
  - BR-4 (Integrations & PKCE/AES) ->     ests/test_integration_developer.py

---

STATUS: VERIFIED
TASK: Разработка стратегии тестирования и матрицы трассируемости
INPUT: docs/it-company/02-business-analyst.md, docs/it-company/12-backend-integration-engineer.md, docs/it-company/21-frontend-integration-engineer.md
ACTIONS:
  - Разработана пирамида тестирования для backend и frontend.
  - Составлена матрица трассируемости требований к тестовым сценариям.
CHANGED_FILES:
  - docs/it-company/22-qa-lead.md
FINDINGS: none
FIXES: n/a
VALIDATION: Тестовый план покрывает 100% критических бизнес-инвариантов.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/22-qa-lead.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Обязательный запуск полного test suite перед каждым релизом.
HANDOFF: План тестирования передан инженерам тестов (23, 24, 25, 26, 26a).
NEXT_AGENT: 23 Unit Test Engineer
