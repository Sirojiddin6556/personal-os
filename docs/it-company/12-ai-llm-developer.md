# Этап 12: AI/LLM Developer — Tool Gateway, AI Advisor, RAG Q&A, Risk Tiers, Plan Apply

STATUS: VERIFIED
NEXT_AGENT: 22-qa-engineer

---

## TASK
Реализация программного комплекса AI Advisor и шлюза безопасности Tool Gateway для персональной операционной системы Personal OS:
1. Создание строго типизированного `ToolGateway` без прямого доступа LLM к базе данных или ORM, с поддержкой 6-уровневой матрицы рисков (`RiskTier`), аудитом в `ai_tool_calls` и атомарным исполнением через `apply_confirmed`.
2. Реализация сервиса `ai_advisor/service.py`:
   - Quick Add Parser (`parse_input`): структурированный парсинг текста с демаркацией недоверенного ввода `<untrusted_external_data>`.
   - Schedule Planner (`create_plan`): чтение состояния через Tool Gateway, планирование расписания, генерация `AIPreviewPlan` с diff изменений и `requires_confirmation=True`.
   - Подтверждение и применение плана (`apply_plan`): атомарное применение изменений и публикация события `ai.plan_applied.v1`.
   - Morning Brief (`generate_morning_brief`) и RAG Q&A (`rag_qa`).
3. Разработка механизма RAG в `knowledge/service.py`:
   - Чанкование заметок `chunk_text` (512 символов, overlap 64).
   - Векторизация `embed_texts` (1536-мерные эмбеддинги text-embedding-3-small с детерминированным офлайн-фоллбэком).
   - Индексация `index_note` с обязательной фиксацией `workspace_id`.
   - Семантический поиск `search_notes` с пре-фильтром `WHERE workspace_id = $1` перед косинусным расстоянием pgvector (Zero Cross-Tenant).
4. Реализация REST API роутера `ai_advisor/router.py` с поддержкой префиксов `/advisor` и `/ai`.
5. Написание набора юнит- и интеграционных тестов с покрытием всех сценариев.

---

## INPUT
- **Документация архитектуры:**
  - `docs/it-company/04-solution-architect.md` — ADR-012 (AI Agent Isolated via Strict Tool Gateway).
  - `docs/it-company/05-security-architect.md` — 6-уровневая матрица рисков (Risk Tiers), демаркаторы Prompt Injection, изоляция RAG pgvector.
  - `docs/it-company/09-backend-architect.md` — структура доменных модулей `ai_advisor` и `knowledge`.
  - `docs/it-company/10-backend-developer.md` — сервисы `task_service`, `calendar_service`, `finance_service`.
- **Существующие модели:**
  - `AIAction`, `AIToolCall`, `AIPlanUndoLog` в `src/domains/ai_advisor/models.py`.
  - `Note`, `NoteChunk` в `src/domains/knowledge/models.py`.

---

## ACTIONS
1. **Создан `apps/api/src/domains/ai_advisor/schemas.py`:**
   - Модели `ParseRequest`, `ParseResult`, `ParseResponse`.
   - Модели `PlanRequest`, `AIPreviewPlan`.
   - Модели `SearchRequest`, `NoteChunkResponse`.
   - Модели `MorningBriefResponse`, `RAGQARequest`, `RAGQAResponse`.
   - Обратно совместимые модели `AIConsultRequest`, `AIConsultResponse`, `AIActionConfirmResponse`, `AIActionUndoResponse`.
2. **Создан `apps/api/src/domains/ai_advisor/llm_client.py`:**
   - 3-уровневый отказоустойчивый клиент: OpenAI (`gpt-4o-mini`) -> Anthropic Claude (`claude-3-5-sonnet`) -> локальный эвристический движок (NLP regex heuristics для работы офлайн/в CI).
   - Функции защиты от Prompt Injection: `wrap_untrusted_data` (оборачивание в `<untrusted_external_data origin="..." sanitized="true">` с HTML-экранированием) и `extract_untrusted_data`.
   - Описание спецификаций инструментов `PLANNER_TOOLS` для Function Calling.
3. **Реализован `apps/api/src/domains/ai_advisor/tool_gateway.py`:**
   - `RiskTier(str, Enum)`: `READ`, `LOW_WRITE`, `MEDIUM_WRITE`, `FINANCIAL`, `BULK`, `DESTRUCTIVE`.
   - Таблица маппинга `RISK_TIER_INT_MAP` для целочисленных ограничений БД (1..6).
   - Класс `ToolCall(tool_name, risk_tier, args)`.
   - Чтение: `get_tasks` (авто-аудит, возврат `list[dict]`), `get_free_busy` (чтение расписания на день), `search_notes` (векторный поиск).
   - Мутации средней опасности: `move_task`, `create_time_block`, `create_task` (возврат `requires_confirmation=True`).
   - Финансовые операции: `post_expense` (строго `requires_confirmation=True`).
   - Деструктивные инструменты: `execute_sql`, `drop_table`, `delete_workspace` — безусловная блокировка с генерацией `ForbiddenError`.
   - Логирование вызовов: `_log_tool_call` с записью в таблицу `ai_tool_calls` (execution_time_ms, arguments, output_payload, status).
   - Диспетчеризация `dispatch`: валидация рисков, проверка отсутствия SQL-инъекций в аргументах, вызов инструментов.
   - Исполнение подтвержденных изменений `apply_confirmed`: атомарный вызов `task_service.update`, `calendar_service.create_time_block`, `finance_service.post_transaction`.
4. **Обновлен `apps/api/src/domains/ai_advisor/policy_engine.py`:**
   - Полная интеграция с `RiskTier` enum и `RISK_TIER_INT_MAP`.
   - Метод `requires_user_confirmation` для определения необходимости Human-in-the-Loop.
5. **Реализован `apps/api/src/domains/ai_advisor/service.py`:**
   - `parse_input`: оборачивание ввода в `<untrusted_external_data>`, обращение к LLM с системным промптом парсера, сохранение записи в `ai_actions`, возврат типизированного `ParseResult`.
   - `create_plan`: чтение состояния задач и календаря через `ToolGateway`, генерация промпта планирования, диспетчеризация предложенных тулов, сохранение плана в статусе `proposed` в таблице `ai_actions`, возврат `AIPreviewPlan`.
   - `apply_plan`: блокировка строки через `with_for_update()`, проверка статуса `proposed`, проверка срока действия `expires_at`, атомарное применение каждого изменения через `gateway.apply_confirmed`, обновление статуса на `applied`, публикация аутбокс-события `ai.plan_applied.v1`.
   - `generate_morning_brief`: утренний дайджест с агрегацией задач, событий и финансовых лимитов.
   - `rag_qa`: вопросно-ответная система над базой знаний с использованием семантического поиска.
   - Обратно совместимый фасад `ai_advisor_service` (`consult`, `confirm_action`, `undo_action`).
6. **Реализован модуль RAG в `apps/api/src/domains/knowledge/service.py`:**
   - `chunk_text(content, chunk_size=512, overlap=64)`: чанкование по границам слов.
   - `embed_texts(texts)`: получение 1536-мерных векторов через OpenAI text-embedding-3-small (или детерминированный генератор псевдослучайных единичных векторов при отсутствии ключа).
   - `index_note(session, workspace_id, note_id, content)`: удаление старых чанков и пакетная вставка новых с обязательным `workspace_id`.
   - `search_notes(session, workspace_id, query, limit=10)`: поиск по косинусному расстоянию pgvector с принудительным пре-фильтром `WHERE workspace_id = $1` (Zero Cross-Tenant).
   - Автоматическая переиндексация заметок в `create_note` и `update_note`.
7. **Реализован `apps/api/src/domains/ai_advisor/router.py`:**
   - `POST /v1/advisor/parse` и `/v1/ai/parse`
   - `POST /v1/advisor/plans` и `/v1/ai/plans`
   - `POST /v1/advisor/plans/{plan_id}/apply` и `/v1/ai/plans/{plan_id}/apply`
   - `POST /v1/advisor/search-notes` и `/v1/ai/search-notes`
   - `POST /v1/advisor/rag-qa`
   - `GET /v1/advisor/brief` и `POST /v1/advisor/brief`
   - `POST /v1/ai/consult`, `/v1/ai/actions/{action_id}/confirm`, `/v1/ai/actions/{action_id}/undo`
8. **Добавлен метод в CalendarService:**
   - `calendar_service.get_events_for_day(session, workspace_id, date)` для удобного чтения событий дня.
9. **Написаны тесты в `apps/api/tests/test_ai_advisor.py`:**
   - 15 всесторонних тестов, покрывающих матрицу рисков, блокировку инъекций и деструктивных операций, работу ToolGateway, Quick Add парсинг, создание и применение планов, изоляцию RAG тенантов, и REST API эндпоинты.

---

## CHANGED_FILES
- `apps/api/src/domains/ai_advisor/schemas.py` — созданы Pydantic v2 схемы для AI Advisor.
- `apps/api/src/domains/ai_advisor/llm_client.py` — создан отказоустойчивый мульти-провайдерный LLM клиент и утилиты защиты от Prompt Injection.
- `apps/api/src/domains/ai_advisor/tool_gateway.py` — переписан безопасный типизированный шлюз с RiskTier, аудитом и `apply_confirmed`.
- `apps/api/src/domains/ai_advisor/policy_engine.py` — обновлен PolicyEngine для работы с RiskTier enum.
- `apps/api/src/domains/ai_advisor/service.py` — реализованы функции `parse_input`, `create_plan`, `apply_plan`, `generate_morning_brief`, `rag_qa`.
- `apps/api/src/domains/ai_advisor/router.py` — реализованы эндпоинты `/advisor/*` и `/ai/*`.
- `apps/api/src/domains/knowledge/service.py` — реализованы функции `chunk_text`, `embed_texts`, `index_note`, `search_notes` (RAG pgvector).
- `apps/api/src/domains/knowledge/router.py` — эндпоинт `/search` перенаправлен на FTS `search_fts`.
- `apps/api/src/domains/calendar/service.py` — добавлен метод `get_events_for_day`.
- `apps/api/src/domains/tasks/service.py` — добавлена поддержка передачи списков статусов в фильтрацию.
- `apps/api/tests/test_ai_advisor.py` — создан тестовый набор из 15 тестов.
- `docs/it-company/12-ai-llm-developer.md` — отчет о выполнении роли AI/LLM Developer.

---

## FINDINGS
1. **Изоляция тенантов в RAG (Zero Cross-Tenant):** Векторный индекс pgvector HNSW в PostgreSQL оптимизирован для поиска по всей таблице, однако для гарантии безопасности мультиарендности критически важно накладывать пре-фильтр `WHERE note_chunks.workspace_id = :workspace_id` непосредственно в SQL-запросе до расчета расстояний `order_by(embedding.cosine_distance(...))`. Это физически исключает утечку данных между пользователями.
2. **Prompt Injection & Data Delimiting:** Любые пользовательские данные из внешних источников (входящие сообщения, темы задач, текст заметок) оборачиваются в XML-демаркаторы `<untrusted_external_data origin="..." sanitized="true">` с предварительным экранированием спецсимволов HTML, что надежно купирует попытки Indirect Prompt Injection.
3. **Безопасность транзакций при исполнении планов:** При вызове `apply_plan` запись плана блокируется строкой `with_for_update()`, проверяется отсутствие истечения срока действия (`expires_at`), и каждая мутация исполняется строго через доменные сервисы ядра, сохраняя аудит-лог и генерируя событие в транзакционный outbox (`ai.plan_applied.v1`).
4. **Устойчивость к отсутствию API-ключей:** Внедрен 3-уровневый каскад (OpenAI -> Anthropic -> NLP Heuristics), позволяющий тестировать всю систему автономно и локально без внешних сетевых вызовов и платных токенов.

---

## VALIDATION
Запуск полного тестового набора через `python -m pytest`:
- `tests/test_ai_advisor.py`: 15 тестов успешно пройдено.
- `tests/test_backend_developer.py`: 7 тестов успешно пройдено.
- `tests/test_health.py`: 1 тест успешно пройден.
- `tests/test_integration_developer.py`: 14 тестов успешно пройдено.
- **Итого:** 37 тестов пройдено, 0 ошибок (100% PASS).

---

## EVIDENCE

```powershell
python -m pytest tests/test_ai_advisor.py
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\Siroj\Projects\personal-os\apps\api
configfile: pyproject.toml
plugins: anyio-4.13.0, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False
collected 15 items

tests\test_ai_advisor.py ...............                                 [100%]
======================= 15 passed in 0.85s ========================
```

Полный запуск:
```powershell
python -m pytest
============================= test session starts =============================
collected 37 items

tests\test_ai_advisor.py ...............                                 [ 40%]
tests\test_backend_developer.py .......                                  [ 59%]
tests\test_health.py .                                                   [ 62%]
tests\test_integration_developer.py ..............                       [100%]

======================= 37 passed in 4.97s =======================
```

---

## REMAINING_ISSUES
Нет. Все требования этапа 12 выполнены в полном объеме.

---

## BLOCKERS
Отсутствуют.

---

## DECISIONS
1. **Единый шлюз с Risk Tiers:** Принято решение зафиксировать 6 уровней риска `RiskTier` (`read`, `low_write`, `medium_write`, `financial`, `bulk`, `destructive`) с автоматическим преобразованием в числовые значения (1..6) для строгой совместимости с Check-констрейнтами схемы PostgreSQL (`chk_ai_actions_risk_tier`).
2. **Двухуровневое пространство маршрутов:** В `router.py` зарегистрированы как маршруты с префиксом `/advisor` (согласно спецификации задачи), так и маршруты `/ai` (для обратной совместимости с существующими фронтенд-интеграциями).
3. **Хранение планов в `ai_actions`:** Планы расписания сохраняются напрямую в таблицу `ai_actions` с типом `schedule_plan` и статусом `proposed`, что позволяет переиспользовать существующие индексы, логику отслеживания срока жизни предложения (`expires_at`) и таблицы отката (`ai_plan_undo_logs`).

---

## HANDOFF
Следующему агенту (QA Engineer) передаются:
- Полностью готовый модуль `apps/api/src/domains/ai_advisor/`:
  - `tool_gateway.py` с типизированными рисковыми инструментами и Human-in-the-Loop валидацией.
  - `service.py` с Quick Add Parser, Schedule Planner, Morning Brief и RAG Q&A.
  - `router.py` с эндпоинтами `/v1/advisor/*`.
  - `llm_client.py` с защитой от Prompt Injection и отказоустойчивым выполнением.
  - `schemas.py` со строгими контрактами Pydantic v2.
- Модуль векторного семантического поиска RAG в `apps/api/src/domains/knowledge/service.py`.
- Набор из 15 автоматизированных тестов в `apps/api/tests/test_ai_advisor.py`.

---

## NEXT_AGENT
22-qa-engineer

---
*Signed off by Role-12 AI/LLM Developer. Verified: 2026-09-11.*
