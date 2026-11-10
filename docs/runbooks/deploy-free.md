# Бесплатный деплой: Render + Neon + Upstash + GitHub Pages

| Часть | Где | Бесплатный лимит |
|---|---|---|
| API (FastAPI, Docker) | Render, `render.yaml` | засыпает после 15 мин простоя, холодный старт ~1 мин |
| PostgreSQL 16 + pgvector | Neon | 0,5 ГБ |
| Redis | Upstash | 10 000 команд/день |
| Telegram Mini App | GitHub Pages, `.github/workflows/pages.yml` | — |

## 1. Neon (база)
1. https://neon.tech → New project, регион Frankfurt (eu-central-1), Postgres 16.
2. Dashboard → Connection string → скопировать строку вида
   `postgresql://user:pass@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
   Расширения (`vector`, `pgcrypto`, `btree_gist`) создаст первая миграция сама.

## 2. Upstash (Redis)
1. https://upstash.com → Create database → Redis, регион Frankfurt.
2. Скопировать URL с TLS: `rediss://default:<password>@<host>.upstash.io:6379`.

## 3. Render (API)
1. https://render.com → войти через GitHub → New → **Blueprint** → репозиторий `personal-os`.
2. Заполнить `DATABASE_URL` (Neon) и `REDIS_URL` (Upstash). `SECRET_KEY` и `MASTER_ENCRYPTION_KEY` Render сгенерирует сам.
3. После деплоя проверить `https://<service>.onrender.com/v1/health` и Swagger `/docs`.
   Миграции применяются при старте (`RUN_MIGRATIONS=1`).

> `MASTER_ENCRYPTION_KEY` шифрует токен бота в базе — не меняйте его после подключения бота.

## 4. GitHub Pages (Mini App)
1. Settings → Pages → Source: **GitHub Actions**.
2. Settings → Secrets and variables → Actions → Variables → `MINIAPP_API_URL = https://<service>.onrender.com/v1`.
3. Actions → «Mini App → GitHub Pages» → Run workflow. Адрес: `https://sirojiddin6556.github.io/personal-os/`.
   Если адрес другой — поправьте `CORS_ORIGINS` и `TELEGRAM_MINIAPP_URL` в Render.

## 5. Аккаунт и бот
1. `/docs` → `POST /v1/auth/register` — создать пользователя; `POST /v1/auth/login` — получить токен, нажать Authorize.
2. `POST /v1/integrations/telegram/connect` с `{"bot_token": "<токен от BotFather>"}`.
   API проверит токен, поставит webhook на `RENDER_EXTERNAL_URL` и кнопку меню «Открыть» на Mini App.
3. Открыть бота → кнопка «Открыть» → войти email/паролем один раз — дальше вход через Telegram.

Токен бота не храните в репозитории и переменных Render — он лежит в базе зашифрованным.
