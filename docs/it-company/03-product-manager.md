# 03. Product Manager (Менеджер продукта)

## 1. Product Backlog & Эпики

### Epic-1: Tasks & Projects Engine (Core MVP)
- **FEAT-1.1**: Унификация 8 статусов задач в схемах, моделях и БД.
- **FEAT-1.2**: Реализация Smart View «Today» (фильтр по датам для активных статусов).
- **FEAT-1.3**: Канбан-доска со столбцами (inbox, todo, in_progress, waiting, done) и скрытием отмененных.
- **FEAT-1.4**: Жизненный цикл проектов (planning, active, on_hold, completed, archived) и запрет создания задач в архиве.

### Epic-2: Immutable Financial Ledger (Core MVP)
- **FEAT-2.1**: Блокировка прямого обновления balance_minor через PATCH.
- **FEAT-2.2**: Операция сверки reconciliation с созданием транзакции и обоснования.
- **FEAT-2.3**: Сторнирование с запретом повторного сторно и защитой от циклов.
- **FEAT-2.4**: Мультивалютные переводы с фиксацией курса и UZS как базовой валютой по умолчанию.

### Epic-3: AI Advisor & Tool Gateway Security (Core MVP)
- **FEAT-3.1**: 6-уровневый Risk Matrix и принудительный Preview для мутаций и финансов.
- **FEAT-3.2**: Хранение Action Proposals в ai_actions с TTL 15 минут и идемпотентностью.
- **FEAT-3.3**: Quick Add NLP с порогом уверенности 0.75, поддержкой сумм (45к, 45 000 UZS) и удалением хардкода RUB.

### Epic-4: Zero-Friction Web Integrations (Core MVP)
- **FEAT-4.1**: Настройка Google OAuth и Telegram Bot Token через Web UI с AES-256-GCM.
- **FEAT-4.2**: Проверка секретного токена Telegram вебхука и deep-link связывание с воркспейсом.
- **FEAT-4.3**: Двусторонняя синхронизация Google Calendar с Delta Sync и 410 Gone full sync.

---

## 2. Roadmap и Definition of Done (DoD)

### Definition of Done (DoD) для каждой функции:
1. Соответствие канонической бизнес-спецификации (BRD).
2. Миграции базы данных протестированы и применены без ошибок.
3. Unit и Integration тесты покрывают позитивные и граничные сценарии (100% прохождение test suite).
4. TypeScript типы во фронтенде полностью согласованы с Pydantic схемами бэкенда (0 ошибок type-check).
5. Все изменения задокументированы в OpenAPI и соответствующих отчётах.

---

STATUS: VERIFIED
TASK: Формирование Product Backlog, эпиков, Roadmap и Definition of Done
INPUT: docs/it-company/01-product-discovery-manager.md, docs/it-company/02-business-analyst.md
ACTIONS:
  - Проект разбит на 4 ключевых эпика с приоритизацией MVP.
  - Определен строгий Definition of Done для всех модулей.
  - Сформирован план релизов и спринтов стабилизации.
CHANGED_FILES:
  - docs/it-company/03-product-manager.md
FINDINGS: none
FIXES: n/a
VALIDATION: Эпики и DoD полностью покрывают все выявленные пробелы аудита.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/03-product-manager.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Приоритет MVP: 8 статусов задач, Immutable Ledger, Tool Gateway confirmation, Web UI integrations.
HANDOFF: Документы этапов 1–3 готовы для этапа 04 Solution Architect.
NEXT_AGENT: 04 Solution Architect
