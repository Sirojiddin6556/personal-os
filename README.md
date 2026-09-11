# Personal OS — Персональная Операционная Система

> **Personal OS** — высокопроизводительная, локально-ориентированная персональная операционная система для управления задачами, календарем, финансами, привычками, базой знаний и повседневным расписанием с интегрированным локальным AI-советником.

---

## 🌟 Ключевые возможности

- ⚡ **Мгновенный ввод (Quick Add):** Добавление задач, событий календаря и расходов менее чем за 3 действия (`Cmd+K` на естественном языке).
- 📋 **Канбан и списки задач:** 6-статусная машина состояний задач (`Inbox` → `Todo` → `Scheduled` → `In Progress` → `Waiting` → `Done`) с защитой от конфликтов версий (`If-Match: ETag`).
- 📅 **Умный календарь и двусторонняя синхронизация:** Интеграция с Google Calendar через дельта-токены (`syncToken`) и автоматическое самозалечивание при `HTTP 410 Gone`.
- 💰 **Целостный финансовый учет:** Неизменяемый журнал проводок (`posted` transactions immutability), целочисленный расчет в минорных единицах (копейки/центы), учет категорий и бюджетов.
- 🤖 **Безопасный AI-советник (AI Advisor):** Утренний брифинг (Morning Brief), автоматическая оптимизация окон дня, семантический RAG-поиск по заметкам (HNSW pgvector) и 6-уровневый Tool Gateway с защитой от Prompt Injection.
- 💬 **Кросс-канальность (Telegram Bot):** Фиксация расходов, создание задач и получение утренней сводки прямо в мессенджере с шифрованием токенов по алгоритму AES-256-GCM.
- 🔒 **Defense-in-Depth Безопасность:** Изоляция рабочих пространств (Multi-Tenancy) на уровне PostgreSQL 16 `FORCE ROW LEVEL SECURITY`.

---

## 🛠 Технологический стек

### Backend & AI:
- **Python 3.12**, **FastAPI**, **Pydantic v2**, **SQLAlchemy 2.0 (Async)**, **Alembic**
- **PostgreSQL 16** + расширение **pgvector** (HNSW векторные индексы cosine similarity)
- **Redis 7** (кэширование, дедупликация вебхуков, брокер очередей)
- **Celery 5.3** + **Celery Beat** (асинхронная обработка Transactional Outbox, периодические синки)
- **OpenAI / Anthropic SDK** через изолированный **Tool Gateway**

### Frontend:
- **Next.js 14+ (App Router)**, **TypeScript 5.4**, **React 18**
- **Tailwind CSS**, дизайн-система токенов (Inter, Light/Dark темы)
- **TanStack Query v5** (управление серверным состоянием, оптимистичные мутации)
- **Zustand** (локальный UI-стейт)
- **@dnd-kit** (плавный 60fps drag-and-drop канбана)
- **Recharts** (визуализация финансов, распределения расходов и трекинга привычек)

### DevOps, SRE & CI/CD:
- **Docker** & **Docker Compose** (многоэтапные образы, непривилегированные пользователи)
- **Nginx Reverse Proxy** (HTTP/2, TLS 1.3, CSP, HSTS, Rate Limiting, WebSockets)
- **Prometheus**, **Alertmanager**, **Grafana** (Четыре Золотых Сигнала: Latency, Traffic, Errors, Saturation)
- **GitHub Actions** (полный пайплайн: Gitleaks, Trivy, Pytest, Vitest, Playwright E2E)

---

## 🚀 Быстрый старт

### 1. Запуск через Docker Compose:
```bash
# Клонирование репозитория
git clone https://github.com/Sirojiddin6556/personal-os.git
cd personal-os

# Подготовка переменных окружения
cp .env.production.example .env

# Запуск всего стека сервисов
docker compose -f docker-compose.prod.yml up -d
```

Приложение будет доступно по адресу:
- Веб-интерфейс: `http://localhost:3000` (или `https://app.personal-os.com`)
- REST API Swagger/OpenAPI: `http://localhost:8000/docs`

---

## 🧪 Запуск тестового прогона

В репозитории настроен единый сквозной скрипт запуска всех 157+ автоматических тестов:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/run-all-tests.ps1

# Linux / macOS (Bash)
./scripts/run-all-tests.sh
```

---

## 📚 Документация

- [Архитектурный обзор (ADR, C4, Bounded Contexts)](docs/architecture.md)
- [Спецификация REST & WebSocket API](docs/api.md)
- [Руководство пользователя](docs/user-guide.md)
- [Руководство разработчика](docs/developer-guide.md)
- [Отчеты 40 ролей IT-компании](docs/it-company/)
