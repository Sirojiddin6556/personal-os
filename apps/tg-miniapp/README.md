# Personal OS — Telegram Mini App

Мобильный интерфейс Personal OS, который открывается внутри Telegram из кнопки меню бота.
Vite + React + TypeScript + TanStack Query, без UI-фреймворков; цвета берутся из темы Telegram.

## Экраны

| Экран | API |
|---|---|
| Сегодня — прогресс дня, брифинг, расписание, главные задачи, привычки | `GET /dashboard/today`, `GET /advisor/brief`, `GET /tasks` |
| AI-план — предпросмотр и применение | `POST /ai/plans`, `POST /ai/plans/{id}/apply` |
| Задачи — фильтры Сегодня / Входящие / Все, карточка задачи | `GET /tasks`, `POST /tasks/{id}/complete`, `PATCH /tasks/{id}` (If-Match) |
| Финансы — баланс, расходы по категориям, операции | `GET /finance/accounts`, `/transactions`, `/categories` |
| Ежедневник — привычки, напоминания, итог дня | `GET/POST /planner/habits…`, `/planner/reminders`, `PUT /planner/journal` |
| «+» быстрое добавление — задача / расход / напоминание одной фразой | `POST /tasks`, `POST /finance/transactions` (Idempotency-Key), `POST /planner/reminders` |

Фразы разбираются на клиенте (`src/lib/parse.ts`) — мгновенный предпросмотр, работает без LLM-ключа.

## Вход

1. Telegram передаёт подписанный `initData`. Приложение отправляет его в `POST /v1/auth/telegram`.
2. API проверяет подпись HMAC-SHA256 токеном бота (глобальный `TELEGRAM_BOT_TOKEN` или токен,
   подключённый в настройках интеграции), срок `auth_date` (`TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`, по умолчанию 24 ч)
   и ищет привязку Telegram ID → workspace.
3. Первый запуск: аккаунт не привязан (`404 TELEGRAM_NOT_LINKED`) → экран входа по email/паролю →
   `POST /v1/auth/telegram/link` сохраняет привязку. Дальше вход без пароля.

JWT хранится только в памяти; при истечении приложение молча перелогинивается через `initData`.

## Разработка

```bash
cd apps/tg-miniapp
npm install
npm run dev          # http://localhost:5174/tg/ , /api → http://localhost:8008/v1
npm test             # парсер быстрого ввода
npm run type-check
```

В обычном браузере (без Telegram) доступен вход по email — удобно для отладки вёрстки.
Чтобы проверить внутри Telegram локально, пробросьте HTTPS-туннель (например, `cloudflared tunnel --url http://localhost:5174`)
и укажите его URL кнопке меню бота.

## Продакшен

- Образ `apps/tg-miniapp/Dockerfile` (nginx со статикой под `/tg/`), сервис `tg_miniapp` в `docker-compose.prod.yml`.
- Внешний nginx проксирует `https://app.personal-os.com/tg/` и ставит CSP, разрешающий
  `telegram.org` и встраивание в `web.telegram.org`.
- В `.env` API задайте `TELEGRAM_MINIAPP_URL=https://app.personal-os.com/tg/` — при подключении бота
  в настройках интеграций API сам поставит кнопку меню «Открыть».
  Или вручную: @BotFather → `/mybots` → Bot Settings → Menu Button.
