# Бесплатный деплой: Render + Neon + Upstash + GitHub Pages

| Часть | Где | Бесплатный лимит |
|---|---|---|
| API (FastAPI, Docker) | Render, `render.yaml` | засыпает после 15 мин простоя, холодный старт ~1 мин |
| PostgreSQL 16 + pgvector | Neon | 0,5 ГБ |
| Redis | Upstash | 10 000 команд/день |
| Веб-приложение + Telegram Mini App | GitHub Pages, `.github/workflows/pages.yml` | — |

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

## 4. GitHub Pages (веб + Mini App)
1. Settings → Pages → Source: **GitHub Actions**.
2. Settings → Secrets and variables → Actions → Variables → `API_URL = https://<service>.onrender.com/v1`.
3. Actions → «Web + Mini App → GitHub Pages» → Run workflow.
   - веб-приложение: `https://sirojiddin6556.github.io/personal-os/`
   - мини-приложение: `https://sirojiddin6556.github.io/personal-os/tg/`
   Если адрес другой — поправьте `CORS_ORIGINS` и `TELEGRAM_MINIAPP_URL` в Render.

## 5. Вход через Google (по желанию)
1. https://console.cloud.google.com → создать проект → **APIs & Services → OAuth consent screen**:
   тип External, название, email; в режиме Testing добавьте себя в Test users (или опубликуйте приложение).
2. **Credentials → Create credentials → OAuth client ID → Web application**.
   Authorized JavaScript origins: `https://sirojiddin6556.github.io` (и `http://localhost:3000` для разработки).
   Redirect URI для входа не нужен.
3. Скопируйте Client ID (`…apps.googleusercontent.com`) в два места:
   - GitHub → Settings → Secrets and variables → Actions → Variables → `GOOGLE_CLIENT_ID`, затем перезапустите Pages-workflow;
   - Render → Environment → `GOOGLE_CLIENT_ID`.
   Client ID — публичное значение; секрет клиента для входа не нужен.

## 6. Аккаунт и бот
1. Войдите на сайт через Google (аккаунт создастся сам) или зарегистрируйтесь в `/docs` → `POST /v1/auth/register`.
2. Веб → Настройки → Интеграции → Telegram: вставьте токен от @BotFather. API поставит webhook и кнопку «Открыть».
3. Там же нажмите «Получить код привязки» и отправьте код боту (или откройте ссылку) — чат привязан.
   Пользователи с паролем могут вместо этого один раз войти email/паролем прямо в мини-приложении.
4. Workflow «Keep API awake» пингует API каждые 10 минут, чтобы бот отвечал сразу и напоминания приходили вовремя.
   Он работает, когда задана переменная `API_URL`.

Токен бота не храните в репозитории и переменных Render — он лежит в базе зашифрованным.
