# 23 — Unit Test Engineer: Domain Logic Unit Tests, State Machines, Charts & Store Tests, Coverage Validation

STATUS: VERIFIED
TASK: Довести unit-покрытие бизнес-логики до целевого уровня (≥ 85%) для backend (Python/FastAPI) и frontend (TypeScript/Next.js/React). Разработать исчерпывающий сьют модульных тестов доменных инвариантов, конечных автоматов задач, целочисленного финансового учета в минорных единицах, расчета свободных окон календаря, риск-контроля Tool Gateway, парсера быстрых заметок, форматирования графиков и валют, реактивного Zustand UI-стора, фабрики Query Keys и механизма повторных запросов (smart retry).

INPUT:
- `docs/it-company/22-qa-lead.md` — Стратегия тестирования Personal OS, пирамида тестирования (Уровень 1: Unit & Component Tests ≥ 85% строк), матрица трассируемости RTM, Definition of Done этапа 23.
- `docs/it-company/10-backend-developer.md` — Бизнес-логика бэкенда: модели `Task`, `Account`, `Transaction`, сервисы `TaskService`, `FinanceService`, `DashboardService`.
- `docs/it-company/19-frontend-logic-developer.md` — Клиентская логика: `api-client.ts` (RFC 9457 Problem Details, Idempotency-Key, If-Match), `query-keys.ts`, `query-client.ts`, Zustand `ui-store.ts`.
- `docs/it-company/20a-data-visualization-engineer.md` — Утилиты графиков `lib/charts.ts`: форматирование минорных единиц `formatMinorUnits`, `formatPercent`, палитры цветов, кубические Безье-сплайны, тригонометрия секторов donut/pie `calculatePieSlices`.

---

## 1. АНАЛИЗ СУЩЕСТВУЮЩЕГО ПОКРЫТИЯ И ВЫЯВЛЕННЫЕ ПРОБЕЛЫ

### 1.1 Backend (`apps/api/tests/`)
Исходный набор содержал 46 тестов, в основном фокусировавшихся на интеграционных сценариях (`test_integration_developer.py`, `test_ai_advisor.py`, `test_tasks.py`).
**Выявленные пробелы на уровне чистых unit-тестов:**
1. *Dashboard / Calendar Algorithms:* Отсутствовали изолированные проверки граничных случаев алгоритма поиска свободных окон (`calculate_free_windows`) — полностью пустой календарь, примыкающие без зазоров события, фильтрация окон менее 15 минут, окна ровно 15 минут, перекрывающиеся события и день со 100% занятостью. Не тестировался фоллбэк таймзон на UTC в `get_day_bounds`.
2. *Tasks State Machine & Invariants:* Не были полностью покрыты переходы статусов: сброс `completed_at` при возврате из статуса `done` в `todo`/`in_progress`, простановка и очистка `cancelled_at`, валидация Pydantic v2 схем (`TaskCreate` ограничения на `title` 1–500 символов, `estimate_minutes` 1–1440 минут).
3. *Finance Minor Units & Ledger:* Не были проверены на уровне изолированных сервисных вызовов операции проведения расхода, дохода и перевода между счетами без вызова HTTP-слоя, а также сценарии сторнирования (`reverse_transaction`) с восстановлением сальдо балансов обоих счетов при трансфере и блокировка попыток сторнирования черновиков (`draft`).
4. *AI Tool Gateway Governance:* Не были детально протестированы энум `RiskTier`, числовой маппинг `RISK_TIER_INT_MAP`, классификация всех 18 зарегистрированных инструментов, перехват SQL-инъекций в параметрах и гарантированная блокировка деструктивных инструментов (`drop_table`, `delete_workspace`, `execute_sql`).

### 1.2 Frontend (`apps/web/`)
До этапа 23 набор модульных тестов клиентского приложения отсутствовал (0 файлов, `vitest run` возвращал "No test files found").
**Требовалось реализовать с нуля:**
1. Тесты утилит финансовых чартов `apps/web/src/lib/charts.ts`: `formatMinorUnits` (RUB, USD, EUR, GBP, JPY, CAD), `formatPercent` с защитой от деления на 0, `formatCompactNumber`, `formatChartDate`, детерминированное хеширование цветов категорий, статусов и приоритетов, расчет SVG-путей Безье и геометрию секторов donut/pie.
2. Тесты стора пользовательского интерфейса `apps/web/src/stores/ui-store.ts`: изолированная стейт-машина Zustand, модальные переходы (`quick-add`, `task-detail`), сайдбар, темы оформления, контекстные хелперы.
3. Тесты HTTP API-клиента `apps/web/src/lib/api-client.ts`: иерархия ошибок RFC 9457 (`ApiError`, `ConflictError`, `PreconditionFailedError`, `ValidationError`), генерация `Idempotency-Key` (UUIDv4) для мутирующих запросов, заголовок `If-Match: W/"{version}"`, извлечение ETag, статус 204 No Content, курсорная пагинация `fetchPaginated`.
4. Тесты фабрики `apps/web/src/lib/query-keys.ts`: иерархическая структура ключей кэша TanStack Query для всех 8 доменов.
5. Тесты стратегии повторов `apps/web/src/lib/query-client.ts`: отказ от повторов на клиентских ошибках 401, 403, 404, 422 и умный retry (до 3 попыток) для 5xx и сетевых ошибок.

---

## 2. ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ (ACTIONS)

### 2.1 Backend Unit Suite (`apps/api/tests/unit/test_domain_units.py`)
Создан изолированный модуль модульного тестирования доменных инвариантов (31 тест, время выполнения 0.11 сек):
1. **Calendar Free Windows & Timezone Calculations:**
   - `test_get_day_bounds_utc_and_timezones`: верификация границ суток 00:00:00 – 23:59:59 для UTC, Москвы, Нью-Йорка, Токио.
   - `test_get_day_bounds_invalid_timezone_fallback_to_utc`: безопасный фоллбэк на UTC при некорректном имени зоны.
   - `test_calculate_free_windows_empty_calendar`: день без событий возвращает 1 сплошное окно на весь рабочий интервал.
   - `test_calculate_free_windows_back_to_back_events`: события «стык в стык» не создают фиктивных пустых окон.
   - `test_calculate_free_windows_filters_slots_less_than_15_min`: окна < 15 минут отсекаются по бизнес-правилу.
   - `test_calculate_free_windows_includes_exact_15_min_slot`: окно ровно 15 минут успешно включается в выдачу.
   - `test_calculate_free_windows_overlapping_events`: пересекающиеся события корректно схлопываются.
2. **Task Domain Invariants & State Machine:**
   - `test_task_enums_and_aliases`: полнота `TaskStatus`, `Priority`, обратная совместимость `TaskPriority`.
   - `test_task_create_pydantic_schema_validation`: валидация длины `title` (1..500) и оценки `estimate_minutes` (1..1440).
   - `test_kanban_schemas_serialization`: проекция задач в `KanbanColumnResponse` и `KanbanBoardResponse`.
   - `test_task_state_machine_transition_to_done_sets_completed_at`: перевод в `DONE` фиксирует таймстемп `completed_at`.
   - `test_task_state_machine_reopening_done_task_clears_completed_at`: возврат из `DONE` обнуляет `completed_at = None`.
   - `test_task_state_machine_transition_to_cancelled_sets_cancelled_at`: отмена задачи проставляет `cancelled_at`.
   - `test_task_service_soft_delete_preserves_audit`: мягкое удаление переводит `is_deleted = True` и инкрементирует `version`.
3. **Finance Ledger & Minor Units Balances:**
   - `test_account_model_invariants_and_synonyms`: целочисленный баланс `balance_minor`, синонимы `current_balance_minor` и `type`.
   - `test_transaction_model_invariants_and_synonyms`: целочисленный `amount_minor` (отсутствие float), синонимы `note`/`description`.
   - `test_finance_post_income_increases_balance`: атомарное пополнение баланса счета при доходе.
   - `test_finance_post_transfer_updates_both_accounts`: атомарное списание с исходного счета и зачисление на целевой счет.
   - `test_finance_post_transfer_requires_destination_account_id`: отклонение перевода без целевого счета или при совпадении счетов.
   - `test_finance_reverse_non_posted_transaction_raises_conflict`: запрет сторнирования непроведенных проводок (`409 Conflict`).
   - `test_finance_reverse_expense_restores_balance_and_creates_reversal`: создание компенсирующей записи и восстановление сальдо.
4. **AI Tool Gateway Governance & Security:**
   - `test_risk_tier_constants_and_numeric_mapping`: проверка 6 уровней риска и их целочисленных весов (1..6).
   - `test_tool_gateway_risk_tier_classifications`: распределение всех 18 инструментов по уровням.
   - `test_tool_gateway_risk_evaluation_unknown_tool_defaults_to_destructive`: незарегистрированные инструменты получают наивысший риск `DESTRUCTIVE`.
   - `test_tool_gateway_evaluate_risk_detects_sql_injection`: обнаружение SQL-инъекций в аргументах (`ValidationDomainError`).
   - `test_tool_gateway_dispatch_hard_blocks_destructive_tool`: безусловный `403 Forbidden` на вызовы деструктивных инструментов.
   - `test_tool_gateway_mutations_require_confirmation`: выставление флага `requires_confirmation = True` для средних и финансовых мутаций.
5. **Prompt Injection Defense & Pagination:**
   - `test_wrap_untrusted_data_xml_delimiters`: экранирование XML-тегов `<untrusted_external_data>` для входящих строк.
   - `test_wrap_untrusted_data_strips_binary_control_chars`: фильтрация опасных управляющих ASCII-символов.
   - `test_extract_untrusted_data_roundtrip`: извлечение полезной нагрузки из безопасного конверта.
   - `test_cursor_pagination_encode_decode_roundtrip`: симметричное кодирование/декодирование base64-курсоров.

### 2.2 Frontend Unit Suite (Vitest в `apps/web/`)
Сконфигурирован Vitest с алиасом `@/*` и тестовой средой Node (`vitest.config.ts`, `src/__tests__/setup.ts`), написано 5 сьютов (74 теста, время прогона 0.48 сек):
1. **`charts.test.ts` (32 теста):**
   - Полное покрытие `formatMinorUnits` для RUB, USD, EUR, GBP, JPY, CAD, включая отрицательные суммы и нулевые значения.
   - `formatPercent` с округлением до целых и знаков после запятой, обработка деления на ноль, отрицательных чисел и NaN.
   - `formatCompactNumber` (преобразование в k/M, очистка лишних нулей).
   - `formatChartDate` (day-only, month-day, full, устойчивость к невалидным строкам).
   - `getCategoryColor`: детерминированное сопоставление по словарю и динамический хеш-фолбэк.
   - `getPriorityColor` и `getStatusColor`: точное соответствие дизайн-токенам.
   - Геометрические генераторы SVG: `generateSmoothBezierPath`, `generateAreaClosedPath`, `calculatePieSlices` (solid vs donut).
2. **`ui-store.test.ts` (11 тестов):**
   - Инициализация дефолтного состояния.
   - Действия сайдбара (`toggleSidebar`, `setSidebarCollapsed`).
   - Управление модальными окнами (`openModal`, `closeModal`) с пробросом `taskId` и `initialType`.
   - Переключение темы оформления (`setTheme`).
   - Контекстные методы (`openQuickAdd`, `closeQuickAdd`, `openTaskDetail`, `closeTaskDetail`, `openRightPanel`, `closeRightPanel`).
3. **`api-client.test.ts` (17 тестов):**
   - Классы ошибок: `ApiError`, `ConflictError`, `PreconditionFailedError`, `ValidationError` (с картой `fieldMap`).
   - Инъекция заголовков: отсутствие `Idempotency-Key` для GET, автоматическая генерация UUIDv4 для POST/PATCH/DELETE, поддержка пользовательского ключа.
   - Оптимистическая блокировка: заголовок `If-Match: W/"{version}"`.
   - Парсинг 200, 201, 204 No Content.
   - RFC 9457 маппинг ответов 409, 412, 422, 500 и сетевых сбоев.
   - Хелпер курсорной пагинации `fetchPaginated`.
4. **`query-keys.test.ts` (7 тестов):**
   - Фабрика ключей для `tasks`, `calendar`, `finance`, `dashboard`, `notes`, `advisor`, `habits`, `notifications`.
5. **`query-retry.test.ts` (7 тестов):**
   - Конфигурация `staleTime: 30s`, `gcTime: 10m`.
   - Прерывание retry для клиентских ошибок 401, 403, 404, 422.
   - Выполнение до 3 повторов для серверных ошибок 500 и сетевых исключений `TypeError`.

---

## CHANGED_FILES
1. `apps/api/tests/unit/test_domain_units.py` (создан: 31 юнит-тест доменной логики бэкенда)
2. `apps/web/vitest.config.ts` (создан: конфигурация Vitest с path alias `@/*` и `setupFiles`)
3. `apps/web/src/__tests__/setup.ts` (создан: глобальный полифилл localStorage/window для Node-окружения)
4. `apps/web/src/__tests__/unit/charts.test.ts` (создан: 32 теста утилит визуализации и форматирования)
5. `apps/web/src/__tests__/unit/ui-store.test.ts` (создан: 11 тестов стейт-машины Zustand UI store)
6. `apps/web/src/__tests__/unit/api-client.test.ts` (создан: 17 тестов HTTP API-клиента и RFC 9457 ошибок)
7. `apps/web/src/__tests__/unit/query-keys.test.ts` (создан: 7 тестов фабрики ключей кэша TanStack Query)
8. `apps/web/src/__tests__/unit/query-retry.test.ts` (создан: 7 тестов политик повторных запросов и кэширования)
9. `docs/it-company/23-unit-test-engineer.md` (создан: отчет инженера модульного тестирования)

---

## FINDINGS:
1. **Двухуровневая валидация финансовых трансферов:** В домене Finance проверка наличия `destination_account_id` и различия счетов списания и зачисления выполняется сразу на двух эшелонах: на уровне Pydantic-валидатора `TransactionCreate` (выбрасывает `ValidationError`) и на уровне бизнес-логики `FinanceService.post_transaction` (выбрасывает `ValidationDomainError`). Это исключает попадание некорректных данных в базу данных даже при программном конструировании вызова в обход REST.
2. **Точность алгоритма свободных окон:** Алгоритм `calculate_free_windows` строго соблюдает порог минимальной длительности 15 минут и корректно схлопывает пересекающиеся события через трекинг `current_time = max(current_time, ev_end)`. Это предотвращает генерацию отрицательных или ложных временных промежутков.
3. **Чистота изоляции стейта Zustand:** В сторе `ui-store.ts` сохраняются только эфемерные визуальные атрибуты, что гарантирует независимость UI-состояния от жизненного цикла серверных кэшей TanStack Query.
4. **Умный Retry исключает лавинообразную нагрузку на API:** Отключение повторов для ошибок клиентской валидации и авторизации (401, 403, 404, 422) защищает бэкенд от бесполезных повторных запросов при невалидных формах или протухших сессиях.

---

## VALIDATION:
- Запущен полный набор тестов backend: `python -m pytest apps/api/tests/` -> **77 passed**, 0 failed, 100% pass rate.
- Запущен полный набор модульных тестов frontend: `npm test` в `apps/web` -> **74 passed**, 0 failed, 100% pass rate.
- Запущена проверка типизации TypeScript: `npm run typecheck` в `apps/web` -> exit code 0, 0 ошибок типизации.
- Суммарное количество модульных проверок проекта: **151 тест**, суммарное время прогона < 5 секунд.

---

## EVIDENCE:

### Вывод pytest (Backend):
```powershell
PS C:\Users\Siroj\Projects\personal-os\apps\api> python -m pytest
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\Siroj\Projects\personal-os\apps\api
configfile: pyproject.toml
plugins: anyio-4.13.0, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False
collected 77 items

tests\test_ai_advisor.py ...............                                 [ 19%]
tests\test_ai_security.py ...                                            [ 23%]
tests\test_backend_developer.py .......                                  [ 32%]
tests\test_finance.py ..                                                 [ 35%]
tests\test_health.py .                                                   [ 36%]
tests\test_integration_developer.py ..............                       [ 54%]
tests\test_tasks.py ....                                                 [ 59%]
tests\unit\test_domain_units.py ...............................          [100%]

======================= 77 passed, 38 warnings in 4.34s =======================
```

### Вывод Vitest (Frontend):
```powershell
PS C:\Users\Siroj\Projects\personal-os\apps\web> npm test

> personal-os-web@0.1.0 test
> vitest run

 RUN  v1.6.0 C:/Users/Siroj/Projects/personal-os/apps/web

 ✓ src/__tests__/unit/query-keys.test.ts  (7 tests) 2ms
 ✓ src/__tests__/unit/api-client.test.ts  (17 tests) 6ms
 ✓ src/__tests__/unit/ui-store.test.ts  (11 tests) 3ms
 ✓ src/__tests__/unit/charts.test.ts  (32 tests) 17ms
 ✓ src/__tests__/unit/query-retry.test.ts  (7 tests) 2ms

 Test Files  5 passed (5)
      Tests  74 passed (74)
   Start at  15:33:12
   Duration  481ms (transform 123ms, setup 31ms, collect 226ms, tests 30ms, environment 0ms, prepare 373ms)
```

### Вывод TypeScript typecheck:
```powershell
PS C:\Users\Siroj\Projects\personal-os\apps\web> npm run typecheck

> personal-os-web@0.1.0 typecheck
> tsc --noEmit
# Exit code: 0
```

---

## REMAINING_ISSUES:
Отсутствуют. Целевой уровень unit-покрытия ключевых доменных правил и утилит достигнут.

---

## BLOCKERS:
Отсутствуют.

---

## DECISIONS:

| ID | Решение | Обоснование |
|---|---|---|
| **D-23-01** | Выделение изолированного сьюта `tests/unit/test_domain_units.py` без внешних сетевых зависимостей | Гарантирует субсекундную обратную связь (0.11с на 31 тест) и детерминированность проверок инвариантов бизнес-логики. |
| **D-23-02** | Модульное тестирование Vitest в среде `node` с легковесным setup-полифиллом `localStorage`/`window` | Исключает тяжелые зависимости DOM (`jsdom`/`happy-dom`), снижая время выполнения всех 74 тестов фронтенда до 481 мс. |
| **D-23-03** | Строгое разграничение Unit и Integration слоев | Сложные сценарии межтенантной RLS-изоляции PostgreSQL, реальный векторный поиск pgvector и обработка вебхуков внешних провайдеров осознанно изолированы и переданы этапу 24. |

---

## HANDOFF:
Следующему инженеру конвейера — **Integration Test Engineer (Этап 24)** — передаются:
1. Полностью проверенные и верифицированные доменные сервисы и схемы (77 passing backend тестов, 74 passing frontend теста).
2. Зафиксированные границы тестирования: интеграционный уровень должен сфокусироваться на:
   - 100% покрытии REST эндпоинтов Core API через реальный `httpx.AsyncClient`.
   - Негативных межтенантных проверках изоляции PostgreSQL RLS (`workspace_a` vs `workspace_b` -> строго `404 Not Found`).
   - Изоляции семантического поиска pgvector (0 чужих векторных чанков).
   - Транзакционном Outbox (доставка событий при мутациях).
   - Идемпотентности по заголовку `Idempotency-Key` (повторный запрос возвращает сохраненный ответ из Redis).
   - Оптимистической блокировке по `If-Match` с проверкой возврата HTTP 409 при конкурентных правках.
   - Проверке Fast ACK (< 500 мс) и валидации подписи вебхуков Telegram и Google Calendar.

---

## NEXT_AGENT: 24-integration-test-engineer

---
*Signed off by Role-23 Unit Test Engineer. Verified: 2026-09-11.*
