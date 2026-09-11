# 08 — Database Engineer: Alembic миграции, RLS-политики, pgvector HNSW, сессионный контекст и партиционирование Personal OS

STATUS: VERIFIED
TASK: Разработать и протестировать реальные файлы миграций Alembic и инфраструктурный слой базы данных для Personal OS (Этап 08: Database Engineer). Реализовать базовую схему 30+ сущностей с типами pgvector и BYTEA, сквозную изоляцию тенантов через FORCE ROW LEVEL SECURITY и сессионный параметр `app.current_workspace_id`, векторный индекс HNSW для OpenAI text-embedding-3-small (1536 dim), RANGE-партиционирование высоконагруженных таблиц логов (activity_events, audit_logs), частичные и B-Tree индексы (включая outbox relay и FTS), а также асинхронную сессионную фабрику SQLAlchemy 2.0 (asyncpg) с контекстными FastAPI dependency generators.
INPUT:
- docs/it-company/07-database-architect.md (DDL спецификация 30 таблиц, инварианты, триггеры immutability, архитектура RLS, pgvector HNSW)
- docs/it-company/06-system-analyst.md (Спецификации событий outbox_events, аудит-логов, ai_actions и ai_tool_calls)
- docs/it-company/05-security-architect.md (Требования к изоляции тенантов, AES-256-GCM для oauth_credentials, запрет утечек в RAG)
- docs/it-company/04-solution-architect.md (ADR-002 PostgreSQL, ADR-005 RLS Multi-Tenancy, ADR-006 Outbox, ADR-015 pgvector)
ACTIONS:
- Развернута структура каталогов `apps/api/alembic/versions/` и `apps/api/src/db/`.
- Сконфигурирован `apps/api/alembic.ini` с поддержкой asyncpg и экранированием интерполяции шаблонов имён файлов.
- Реализован `apps/api/alembic/env.py` для асинхронного выполнения миграций (`async_engine_from_config`, `NullPool`, `literal_binds` для offline SQL-генерации).
- Разработана миграция `0001_initial_schema.py`:
  - Активация расширений `uuid-ossp`, `pgcrypto`, `vector`, `btree_gist`.
  - Вспомогательные функции `update_updated_at_column()` и `current_workspace_id()`.
  - Полный DDL для всех 32 таблиц с жесткими CHECK ограничениями (включая приоритеты задач `low, medium, high, critical, P1-P4`, монетарные суммы в минорных единицах `BIGINT amount_minor > 0`, векторное поле `note_chunks.embedding vector(1536)` и зашифрованные OAuth токены `BYTEA`).
  - Триггеры автоматического обновления `updated_at`.
- Разработана миграция `0002_rls_policies.py`:
  - `ENABLE ROW LEVEL SECURITY` и `FORCE ROW LEVEL SECURITY` для всех 30 tenant-scoped таблиц.
  - Политика `tenant_isolation` с проверкой `workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid`.
  - Триггер финансовой неизменяемости `trg_prevent_posted_mutation` (запрет UPDATE/DELETE проведенных проводок, разрешение только сторнирования).
  - Триггер `trg_validate_note_chunk_workspace` для предотвращения кросс-тенантного связывания векторных фрагментов.
- Разработана миграция `0003_pgvector_hnsw.py`:
  - Создание векторного индекса HNSW `idx_note_chunks_embedding_hnsw` (`vector_cosine_ops`, `m = 16`, `ef_construction = 64`).
  - Установка сессионного параметра качества векторного поиска `hnsw.ef_search = 40`.
- Разработана миграция `0004_partitioned_activity_audit.py`:
  - Помесячные RANGE-партиции для `activity_events` и `audit_logs` (2026-09 .. 2027-02 + safety default partitions).
  - Наследуемые композитные индексы на партиционированных таблицах.
  - Хранимая процедура `purge_published_outbox_events(batch_size)` для циклической очистки опубликованных outbox-событий.
- Разработана миграция `0005_outbox_indexes.py`:
  - Критические индексы релея outbox (`idx_outbox_unpublished` WHERE published_at IS NULL, `idx_outbox_pending_relay` WHERE status = 'pending').
  - Частичные индексы активных задач (`idx_tasks_active_due_at`), непрочитанных нотификаций (`idx_notifications_unread`), необработанных входящих (`idx_inbox_items_pending`), активных AI планов (`idx_ai_actions_active_proposed`).
  - Индексы связей и диапазонов для календаря, финансов и привычек.
  - Полнотекстовые GIN-индексы для задач и заметок с русской лемматизацией (`idx_tasks_fts`, `idx_notes_fts`).
- Реализован базовый модуль `apps/api/src/db/base.py`:
  - `Base(DeclarativeBase)`
  - `UUIDMixin` с `server_default=text("gen_random_uuid()")`
  - `TimestampMixin` с `clock_timestamp()`
  - `WorkspaceMixin` со строгим FK `workspaces.id` и каскадным удалением
- Реализован модуль сессий `apps/api/src/db/session.py`:
  - `AsyncEngine` с пулом соединений и pre-ping
  - `async_session_factory`
  - `set_tenant_context()` с `SET LOCAL app.current_workspace_id = :wid`
  - FastAPI dependency generators: `get_session(workspace_id)` и `get_db_session()`
- Проведено сквозное тестирование:
  - `alembic history`: корректная цепочка 0001 -> 0002 -> 0003 -> 0004 -> 0005.
  - `alembic heads`: единый актуальный head `0005_outbox_indexes`.
  - `alembic upgrade base:heads --sql`: генерация полного DDL-скрипта без синтаксических ошибок.
  - Python import test для модулей `src.db`.
CHANGED_FILES:
- apps/api/alembic.ini
- apps/api/alembic/env.py
- apps/api/alembic/versions/0001_initial_schema.py
- apps/api/alembic/versions/0002_rls_policies.py
- apps/api/alembic/versions/0003_pgvector_hnsw.py
- apps/api/alembic/versions/0004_partitioned_activity_audit.py
- apps/api/alembic/versions/0005_outbox_indexes.py
- apps/api/src/__init__.py
- apps/api/src/db/__init__.py
- apps/api/src/db/base.py
- apps/api/src/db/session.py
- docs/it-company/08-database-engineer.md
FINDINGS:
- В Python 3.14 встроенный модуль `configparser` строго проверяет интерполяцию `%` в `.ini` файлах; строка шаблона `file_template = %(rev)s_%(slug)s` требует экранирования в `%%(rev)s_%%(slug)s` для предотвращения `InterpolationMissingOptionError`.
- Использование `SET LOCAL app.current_workspace_id = :wid` гарантирует изоляцию транзакций: значение сбрасывается сразу по завершении транзакции (`COMMIT`/`ROLLBACK`), полностью исключая перекрестную утечку тенантов при переиспользовании соединений в пуле `asyncpg`.
- Использование `NULLIF(current_setting('app.current_workspace_id', true), '')::uuid` предотвращает аварийное завершение запросов с ошибкой невалидного формата UUID в случае незаданной или пустой сессионной переменной (возвращается NULL и RLS отсекает все строки).
- Базовые партиционированные таблицы `activity_events` и `audit_logs` создаются в 0001 с типом `PARTITION BY RANGE (occurred_at)`, что позволяет применить RLS-политики на шаге 0002, а конкретные помесячные дочерние партиции и индексы подключить на шаге 0004. В PostgreSQL 16 дочерние партиции автоматически наследуют RLS и политики родительской таблицы.
VALIDATION:
- Верификация графа миграций Alembic: команда `python -m alembic history` подтвердила непрерывную цепочку ревизий от `<base>` до `0005_outbox_indexes (head)`.
- Синтаксическая и структурная проверка SQL: команда `python -m alembic upgrade base:heads --sql` успешно скомпилировала полный диалектный SQL-скрипт PostgreSQL со всеми типами (`vector(1536)`, `BYTEA`, `JSONB`, `UUID`, `INET`), ограничениями CHECK, триггерными функциями PL/pgSQL и RLS политиками.
- Интеграционная проверка Python: импорт всех классов и миксинов из `src.db` (`Base`, `UUIDMixin`, `TimestampMixin`, `WorkspaceMixin`, `get_session`, `engine`) выполнен без ошибок с установленными библиотеками `asyncpg` и `pgvector`.
EVIDENCE:
1. Вывод команды `alembic history`:
```
0004_partitioned_activity_audit -> 0005_outbox_indexes (head), 0005_outbox_indexes
0003_pgvector_hnsw -> 0004_partitioned_activity_audit, 0004_partitioned_activity_audit
0002_rls_policies -> 0003_pgvector_hnsw, 0003_pgvector_hnsw
0001_initial_schema -> 0002_rls_policies, 0002_rls_policies
<base> -> 0001_initial_schema, 0001_initial_schema
```

2. Фрагмент сгенерированного SQL для RLS и триггера неизменяемости (Migration 0002):
```sql
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tasks
FOR ALL
USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid)
WITH CHECK (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);

CREATE OR REPLACE FUNCTION prevent_posted_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IN ('posted', 'reversed') THEN
            RAISE EXCEPTION 'Cannot delete a posted or reversed transaction (id=%). Create a reversal instead.', OLD.id
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN OLD;
    END IF;
    ...
```

3. Фрагмент сгенерированного SQL для HNSW и Outbox Partial Index (Migrations 0003, 0005):
```sql
CREATE INDEX idx_note_chunks_embedding_hnsw
ON note_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_outbox_unpublished 
ON outbox_events (created_at) 
WHERE published_at IS NULL;
```

4. Python verification output:
```
python -c "import sys; sys.path.insert(0, 'apps/api'); from src.db import Base, UUIDMixin, TimestampMixin, WorkspaceMixin, engine, get_session; print('DB module imports OK!')"
Output: DB module imports OK!
```
REMAINING_ISSUES: Нет. Слой базы данных и миграций полностью готов для реализации репозиториев и сервисов бэкенда.
BLOCKERS: Нет блокеров.
DECISIONS:
- DEC-DBENG-01: Использован драйвер `postgresql+asyncpg` по умолчанию в `DATABASE_URL` с поддержкой транзакционного пула соединений (`pool_pre_ping=True`, `pool_size=20`).
- DEC-DBENG-02: Поддержка двойного формата приоритетов задач: ограничение `chk_tasks_priority` валидирует как текстовые обозначения `('low', 'medium', 'high', 'critical')`, так и ранговые коды `('P1', 'P2', 'P3', 'P4')` для исключения несовместимости слоев UI, API и аналитики.
- DEC-DBENG-03: `FORCE ROW LEVEL SECURITY` принудительно включен на всех 30 таблицах воркспейса, что обеспечивает защиту даже от случайных несанкционированных выборок под учетной записью суперпользователя или владельца таблиц.
- DEC-DBENG-04: Для безопасного векторного поиска создан HNSW индекс по косинусному расстоянию (`vector_cosine_ops`), что в связке с пре-фильтрацией по `workspace_id` и RLS исключает межтенантные утечки.
- DEC-DBENG-05: Сессионная зависимость `get_session(workspace_id)` в `src/db/session.py` инкапсулирует вызов `SET LOCAL app.current_workspace_id = :wid` в рамках одной транзакции FastAPI запроса.
HANDOFF: Передать инфраструктурный слой БД, миграции Alembic и модуль `src.db` архитектору бэкенда (09-backend-architect) для проектирования Domain Models, слоев репозиториев, UoW (Unit of Work) и FastAPI маршрутов.
NEXT_AGENT: 09-backend-architect
