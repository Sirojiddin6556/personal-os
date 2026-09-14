# Personal OS: Staging & E2E Verification Runbook

## 1. Обзор и архитектурный контекст

Данный регламент описывает процедуру комплексного сквозного (End-to-End) и Staging-тестирования внешних интеграций **Personal OS**:
- **Telegram Bot Gateway** (Opaque UUID Webhook `POST /v1/webhooks/telegram/{webhook_id}`, Fast ACK `<500ms`, Redis Deduplication, Secret Token Validation, AES-256-GCM Token Encryption, Polling Fallback).
- **Google Calendar Integration** (OAuth 2.0 PKCE Flow, AES-256-GCM Token Encryption, Delta Token Incremental Sync, 410 Gone Resilience, Webhook Notifications).

---

## 2. Конфигурация Staging-контура

### 2.1. Топология портов и сетевые параметры

| Компонент | Локальный порт | Staging URL / Туннель | Описание |
|---|---|---|---|
| **API Host** | `8008` | `https://api-staging.yourdomain.com` (или ngrok) | Основной REST/WebSocket API |
| **API Docker** | `8000` | Внутренняя сеть контейнеров | Проксируется на порт 8008 хоста |
| **Web UI** | `3000` | `https://app-staging.yourdomain.com` | Next.js Frontend |
| **PostgreSQL** | `5432` | `localhost:5432` / Cloud SQL | База данных с RLS (`personal_os_staging`) |
| **Redis** | `6379` | `localhost:6379` | Кэш, дедупликация и сессии |

### 2.2. Переменные окружения Staging (`.env.staging`)

```bash
# Server & Ports
PORT=8008
ENVIRONMENT=staging
API_V1_PREFIX=/v1
SECRET_KEY=staging-master-jwt-secret-key-min-32-chars-2026
AES_GCM_SECRET_KEY=staging-master-aes-key-for-oauth-and-telegram-bot

# Database & Redis
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/personal_os_staging
REDIS_URL=redis://localhost:6379/0

# Public URLs for Webhooks & Callbacks
TELEGRAM_WEBHOOK_BASE_URL=https://api-staging.yourdomain.com
GOOGLE_REDIRECT_URI=https://api-staging.yourdomain.com/v1/integrations/google/callback

# Test Credentials (Отдельные staging-аккаунты, НЕ production!)
STAGING_TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz_staging
STAGING_GOOGLE_CLIENT_ID=staging-client-id.apps.googleusercontent.com
STAGING_GOOGLE_CLIENT_SECRET=GOCSPX-stagingClientSecret12345
```

> [!IMPORTANT]
> **Требования к Google Cloud Console Redirect URI:**
> В разделе *APIs & Services > Credentials > OAuth 2.0 Client IDs* должен быть указан **ровно один в один**:
> `https://<public-domain>/v1/integrations/google/callback`
> Не допускаются: лишний слеш в конце, несоответствие протокола (`http` вместо `https`) или расхождение поддоменов.

---

## 3. Telegram E2E Сценарии (14 контрольных точек)

### 3.1. Схема жизненного цикла

```
POST /v1/integrations/telegram/connect
    ↓
1. Валидация токена через getMe
    ↓
2. Генерация webhook_id (UUID) & webhook_secret
    ↓
3. Регистрация в Telegram API: setWebhook(url="https://.../v1/webhooks/telegram/{webhook_id}", secret_token=...)
    ↓
4. Запись в БД: status="connected", mode="webhook", webhook_registered=true, enc_token=AES-GCM
    ↓
5. Прием входящего update от Telegram: POST /v1/webhooks/telegram/{webhook_id}
    ↓
6. Проверка X-Telegram-Bot-Api-Secret-Token (constant-time)
    ↓
7. Fast ACK ({"ok": true}) < 500ms
    ↓
8. Redis SETNX дедупликация update_id
    ↓
9. Асинхронный BackgroundTask: классификация команды и запись в InboxItem / Tasks
```

### 3.2. Матрица проверок Telegram E2E

| № | Сценарий | Ожидаемый результат | Критерий приёмки |
|---|---|---|---|
| 1 | Подключение с валидным HTTPS URL | Регистрация в Telegram API, `webhook_registered: true`, `mode: "webhook"` | `HTTP 200`, `webhook_id` сгенерирован (UUID) |
| 2 | Проверка URL вебхука | URL в Telegram имеет вид `.../telegram/{webhook_id}` | Bot token **отсутствует** в URL и логах |
| 3 | Прием реального сообщения | Создание задачи или подтверждение расхода | Сообщение доставлено, `InboxItem` создан |
| 4 | Проверка Secret Token | Заголовок `X-Telegram-Bot-Api-Secret-Token` совпадает | Успешная обработка, Fast ACK `<500ms` |
| 5 | Повтор того же `update_id` | Идемпотентный пропуск повторной обработки | `{"ok": true}` возвращен, обработчик не вызывается повторно |
| 6 | Запрос с неизвестным `webhook_id` | Отклонение несуществующего идентификатора | `HTTP 404 Not Found` |
| 7 | Запрос с неверным Secret Token | Отклонение неавторизованного вызова | `HTTP 403 Forbidden` |
| 8 | Ошибка Telegram `setWebhook` | Корректный fallback без падения сервера | `mode: "polling"`, `webhook_registered: false` |
| 9 | Подключение без HTTPS URL | Автоматический переход в polling | `mode: "polling"`, `webhook_registered: false` |
| 10 | Отключение бота (`DELETE`) | Вызов `deleteWebhook` в Telegram Bot API | `status: "disconnected"`, `enc_token` очищен |
| 11 | Проверка инвалидации старого UUID | Попытка отправки на старый `webhook_id` | `HTTP 404 Not Found` |
| 12 | Повторное подключение (`Reconnect`) | Генерация нового `webhook_id` | Новый UUID отличается от предыдущего |
| 13 | Перезапуск API сервиса | Сохранение состояния подключенной интеграции | `GET /status` возвращает `connected` и валидный `webhook_id` |
| 14 | Недоступность Redis | Graceful fallback на in-memory дедупликацию | Fast ACK `<500ms`, система не падает |

---

## 4. Google OAuth E2E Сценарии

### 4.1. Схема OAuth 2.0 Flow

```
POST /v1/integrations/google/configure (Сохранение Client ID/Secret)
    ↓
GET /v1/integrations/google/authorize (Генерация PKCE S256 verifier/challenge и state JWT)
    ↓
Пользователь проходит Google Consent Screen
    ↓
GET /v1/integrations/google/callback?code=...&state=...
    ↓
1. Валидация state JWT и расшифровка PKCE verifier
2. Обмен code на access_token и refresh_token
3. Шифрование токенов AES-256-GCM и сохранение в OAuthCredential
    ↓
POST /v1/integrations/google/sync (Инкрементальная синхронизация событий)
    ↓
DELETE /v1/integrations/google/disconnect (Отзыв токенов и очистка)
```

### 4.2. Матрица негативных и граничных проверок Google OAuth

| Сценарий | Тестовое воздействие | Ожидаемый результат |
|---|---|---|
| **Неправильный / поддельный `state`** | Передача некорректной подписи в параметре `state` | `HTTP 400/403 Invalid OAuth state parameter` |
| **Истекший `state`** | Передача `state` со сроком жизни `exp > 5 минут` | `HTTP 400 Expired state` |
| **Повторное использование `code`** | Повторный вызов callback с использованным auth code | Контролируемая ошибка обмена токенов без утечки stack trace |
| **Отказ пользователя (`error=access_denied`)** | Переход в callback с параметром ошибки от Google | Обработка отказа и редирект на экран настроек со статусом |
| **Несовпадающий `redirect_uri`** | Несоответствие между `GOOGLE_REDIRECT_URI` и настройкой в Google | Telegram/Google возвращает `redirect_uri_mismatch`, API отдает читаемый Problem Details |
| **Отсутствие `refresh_token`** | Авторизация без параметра `access_type=offline` | Предупреждение и требование повторной авторизации с prompt=consent |
| **Истечение токена синхронизации (`410 Gone`)** | Эмуляция инвалидации Google `sync_token` | Автоматический fallback: сброс токена и запуск `full_sync` |
| **Отключение интеграции** | Вызов `DELETE /v1/integrations/google/disconnect` | Отзыв токена в Google API, удаление локальных ключей и связей |

---

## 5. Запуск автоматизированных Staging E2E тестов

Тесты с реальными внешними сервисами отделены маркерами `@pytest.mark.staging` и `@pytest.mark.external`.

```bash
# 1. Запуск стандартных тестов (mocked / unit / fast):
python -m pytest

# 2. Запуск Staging E2E тестов (требует активный HTTPS туннель и переменные окружения):
python -m pytest tests/e2e -m staging -v

# 3. Запуск отдельного E2E сценария Telegram:
python -m pytest tests/e2e/test_telegram_staging.py -v

# 4. Запуск отдельного E2E сценария Google OAuth:
python -m pytest tests/e2e/test_google_oauth_staging.py -v
```

---

## 6. Чеклист формирования E2E-артефакта прогона

Перед фиксацией релиза и переходом к интерфейсам сформировать протокол прогона:

- [ ] **Commit SHA:** `git rev-parse HEAD`
- [ ] **Дата и время:** ISO 8601 UTC
- [ ] **Окружение:** `staging`
- [ ] **Версия Python / Node:** `Python 3.12+`, `Node 20+`
- [ ] **Pytest результат:** Все тесты `PASSED` (0 errors, 0 warnings, coverage $\ge 60\%$)
- [ ] **TypeScript проверка:** `npm run type-check` $\rightarrow$ 0 errors
- [ ] **Alembic current:** `0008_reconcile_proj_status (head)`
- [ ] **Liveness Check:** `GET /v1/health/live` $\rightarrow$ `200 OK`
- [ ] **Readiness Check:** `GET /v1/health/ready` $\rightarrow$ `200 OK` (`database: ok, crypto: ok`)
- [ ] **Telegram Webhook Info:** подтвержден `url: https://.../v1/webhooks/telegram/{webhook_id}` без секретов
- [ ] **Google OAuth Callback:** подтвержден успешный обмен без вывода токенов в логах
- [ ] **Санитизация:** проверено отсутствие токенов, ключей и персональных данных в логах и артефактах
