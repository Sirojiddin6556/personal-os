# Архитектура Personal OS

## 1. Концепция и Bounded Contexts

Personal OS спроектирована как модульный монолит (Modular Monolith) с 12 строго разграниченными контекстами:
1. **Identity & Tenancy:** Пользователи, мульти-тенантные рабочие пространства (`workspaces`), членство, RBAC.
2. **Tasks & Planning:** Задачи, приоритеты, дедлайны, 6-статусный канбан.
3. **Calendar:** События, тайм-блоки дня, интеграция с внешними календарями.
4. **Finance:** Счета, категории, неизменяемый бухгалтерский журнал (`Transaction`), бюджеты.
5. **Knowledge:** Иерархические заметки, чанкирование текста, pgvector HNSW семантический поиск.
6. **Habits:** Трекинг привычек, стрики, статистика выполнения.
7. **Integration Hub:** Google Calendar OAuth2, Telegram Bot webhook, шифрование токенов (AES-256-GCM).
8. **AI Advisor & Policy Engine:** Анализ расписания, утренний брифинг, 6-уровневый Tool Gateway, RAG.
9. **Notifications:** Push, WebSockets, Telegram каналы доставки с соблюдением Quiet Hours.
10. **Inbox:** Единая точка захвата необработанных мыслей и заметок.
11. **Activity & Audit:** Неизменяемый журнал аудита действий и доменных событий.
12. **Outbox Relay:** Transactional Outbox для надежной асинхронной доставки событий в Celery.

## 2. Изоляция данных (PostgreSQL Row Level Security)

Все таблицы данных содержат столбец `workspace_id: UUID NOT NULL`. Изоляция гарантируется на уровне ядра СУБД:
```sql
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tasks
  USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid);
```

## 3. Transactional Outbox Pattern

Каждая мутация домена фиксируется в одной ACID-транзакции с записью в таблицу `outbox_events`. Фоновый релей считывает неопубликованные записи и пересылает в очереди Celery воркеров, обеспечивая гарантию доставки *At-Least-Once*.
