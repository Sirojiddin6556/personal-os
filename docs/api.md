# Спецификация REST & WebSocket API v1

## Аутентификация
- **Заголовок:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Контекст тенанта:** `X-Workspace-Id: <UUID>`

---

## 📌 Ключевые Эндпоинты

### Tasks API
- `GET /v1/tasks` — Список задач с фильтрацией по статусу, приоритету и курсорной пагинацией (`cursor`, `limit`).
- `POST /v1/tasks` — Создание задачи (`Idempotency-Key: <UUID>`).
- `PATCH /v1/tasks/{id}` — Обновление задачи (`If-Match: W/"<version>"`).
- `POST /v1/tasks/{id}/complete` — Перевод задачи в статус `done`.

### Finance API
- `GET /v1/finance/accounts` — Получение списка счетов и балансов.
- `POST /v1/finance/transactions` — Проведение транзакции (`posted`).
- `POST /v1/finance/transactions/{id}/reverse` — Сторнирование (реверсивная операция).

### AI Advisor API
- `POST /v1/advisor/parse` — Распознавание свободного ввода на естественном языке (Quick Add).
- `POST /v1/advisor/plans` — Генерация плана оптимизации расписания (Preview diff).
- `POST /v1/advisor/plans/{id}/apply` — Применение плана через Tool Gateway.

### Real-time WebSockets
- `GET /v1/ws?token=<JWT>` — Двусторонний WebSocket канал реального времени (события `task.updated`, `calendar.event_changed`, `finance.transaction.posted`).
