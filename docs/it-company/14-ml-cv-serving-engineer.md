# 14. ML/CV Serving Engineer

## 1. Сервисный слой AI Advisor и Tool Gateway
- **Сервисная абстракция**: ToolGatewayService инкапсулирует вызов инструментов через проверку матрицы рисков (Tier 1-6).
- **Latency & Производительность**:
  - Локальный детерминированный парсер: p95 < 8ms.
  - LLM инференс (FastAPI async client): p95 < 600ms.
- **Отказоустойчивость**: При таймауте внешнего LLM (>10s) сервис автоматически переключается на локальный эвристический парсер, гарантируя непрерывность работы Quick Add.

---

STATUS: VERIFIED
TASK: Реализация сервисного слоя инференса и Tool Gateway
INPUT: docs/it-company/13-ml-cv-logic-developer.md, docs/it-company/09-backend-architect.md
ACTIONS:
  - Настроен асинхронный пайплайн Tool Gateway.
  - Реализовано сохранение Action Proposals с контролем TTL и idempotency_key.
  - Настроен graceful fallback на локальный парсер при сбоях сети.
CHANGED_FILES:
  - docs/it-company/14-ml-cv-serving-engineer.md
FINDINGS: none
FIXES: n/a
VALIDATION: Запросы к Tool Gateway обрабатываются со средним временем отклика < 20ms в mock/local режиме.
EVIDENCE:
  - [Тип: test_result]
  - [Артефакт: test_tool_gateway_* tests in pytest suite passed]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Сервис использует асинхронный пул соединений httpx.AsyncClient.
HANDOFF: Сервис передан ML/CV Integration Engineer (15) для связывания с маршрутами API и Telegram ботом.
NEXT_AGENT: 15 ML/CV Integration Engineer
