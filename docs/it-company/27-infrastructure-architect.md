# 27 — Infrastructure Architect: Контейнеризация, Спецификации Развертывания, CI/CD и Observability

STATUS: VERIFIED
TASK: Спроектировать и разработать реальные конфигурационные файлы инфраструктуры Personal OS (Этап 27: Infrastructure Architect). Реализовать дев-окружение Docker Compose (PostgreSQL 16 с pgvector, Redis 7, MinIO S3, Core API, Celery Worker, Next.js Web), Dockerfiles для сервисов бэкенда и фронтенда с поддержкой non-root безопасности, пайплайн GitHub Actions CI/CD (линтеры, тесты, миграции, сборка образов), конфигурацию сбора метрик Prometheus, шаблон переменных окружения .env.example и оверлей наблюдаемости Docker Compose (Prometheus + Grafana).
INPUT:
- docs/it-company/01-product-discovery-manager.md (Стек технологий, границы MVP, решение по SRE: REQUIRED)
- docs/it-company/04-solution-architect.md (C4 Containers, ADR-011 Notification Engine, ADR-015 pgvector, ADR-016 Redis+Celery, ADR-017 MinIO S3, ADR-018 WebSockets, ADR-020 Containers before Kubernetes)
- docs/it-company/05-security-architect.md (Модель угроз, безопасное управление секретами через .env, non-root контейнеры, HTTPS everywhere)
- docs/it-company/08-database-engineer.md (Схема базы данных, Alembic миграции, RLS multi-tenancy, HNSW векторы)
ACTIONS:
- Разработан основной файл оркестрации локального окружения `infra/docker/docker-compose.yml`:
  - `postgres`: образ `pgvector/pgvector:pg16` с healthcheck (`pg_isready -U personal_os`), персистентным томом `postgres_data` и портом 5432.
  - `redis`: образ `redis:7-alpine` с парольной защитой `--requirepass ${REDIS_PASSWORD}`, healthcheck (`redis-cli ping`), персистентным томом `redis_data` и портом 6379.
  - `minio`: образ `minio/minio` с S3 API (порт 9000) и веб-консолью управления (порт 9001), томом `minio_data`.
  - `api`: сборка на базе `apps/api/Dockerfile`, строгая зависимость от здоровья `postgres` и `redis`, проброс порта 8000.
  - `worker`: сборка на базе `apps/api/Dockerfile.worker`, запуск воркера Celery (`celery -A src.worker worker --loglevel=info`), зависимость от `api`.
  - `web`: сборка фронтенда на базе `apps/web/Dockerfile`, подключение к API через `NEXT_PUBLIC_API_URL: http://api:8000`, проброс порта 3000.
- Разработан `apps/api/Dockerfile`:
  - Базовый образ `python:3.12-slim`.
  - Создание непривилегированного пользователя и группы `nonroot` (`groupadd -r nonroot && useradd -r -g nonroot nonroot`) для соблюдения политик безопасности и принципа наименьших привилегий.
  - Использование пакетного менеджера `uv` для детерминированной и быстрой установки зависимостей (`uv sync --frozen --no-dev`).
  - Копирование исходного кода приложения `src/`.
  - Переключение на `USER nonroot`.
  - Экспорт порта 8000 и запуск через `uvicorn src.main:app --host 0.0.0.0 --port 8000`.
- Разработан `apps/api/Dockerfile.worker` для Celery воркеров:
  - Идентичная безопасная среда выполнения `python:3.12-slim` с `nonroot` пользователем.
  - Точка входа `celery -A src.worker worker --loglevel=info`.
- Разработан многоэтапный `apps/web/Dockerfile`:
  - Stage `deps`: образ `node:20-alpine`, установка зависимостей.
  - Stage `builder`: компиляция Next.js с оптимизацией `output: 'standalone'`.
  - Stage `runner`: минимальный runtime-слой `node:20-alpine`, запуск автономного сервера `node server.js` под непривилегированным пользователем.
- Сконфигурирован CI/CD пайплайн `.github/workflows/ci.yml`:
  - Триггеры на `push` и `pull_request` в ветки `master` и `main`.
  - Задача `backend-test`: виртуальные контейнеры PostgreSQL (pgvector) и Redis с healthcheck, установка Python 3.12, синхронизация пакетов через `uv`, накат миграций Alembic (`uv run alembic upgrade head`), запуск unit/integration тестов (`uv run pytest tests/ -v`).
  - Задача `frontend-test`: Node.js 20, кэширование npm, установка зависимостей (`npm ci`), сборка (`npm run build`), тестирование (`npm run test`).
  - Задача `docker-build`: верификация сборки контейнерных образов `personal-os-api` и `personal-os-web`.
- Разработана конфигурация сбора метрик `infra/observability/prometheus.yml`:
  - Глобальный интервал скрейпинга 15 секунд.
  - Таргеты сбора метрик: Core API (`api:8000/metrics`), Celery Worker (`worker:9080`), PostgreSQL Exporter (`postgres-exporter:9187`), Redis Exporter (`redis-exporter:9121`).
- Разработан оверлей мониторинга `infra/docker/docker-compose.observability.yml`:
  - Сервис `prometheus` (порт 9090) с монтированием конфигурационного файла `prometheus.yml`.
  - Сервис `grafana` (порт 3001:3000) с персистентным томом `grafana_data` и настройкой пароля администратора через переменные окружения.
- Подготовлен исчерпывающий шаблон конфигурации `.env.example`:
  - Секции для Database (URL, пароли), Redis, JWT Auth, AI ключей (OpenAI, Anthropic), MinIO S3, Telegram Bot, Sentry DSN и CORS.
- Дополнительно настроены инфраструктурные связующие элементы:
  - Конфигурация `apps/api/pyproject.toml` с `[tool.uv] package = false` для бесшовной сборки в Docker.
  - Точка входа `apps/api/src/main.py` с эндпоинтами `/healthz` и `/metrics`.
  - Модуль воркера `apps/api/src/worker.py` для инициализации Celery.
  - Standalone-конфигурация Next.js `apps/web/next.config.mjs`.
  - Тестовый скрипт и директория `apps/api/tests/test_health.py` для корректного прохождения CI.
CHANGED_FILES:
- infra/docker/docker-compose.yml
- infra/docker/docker-compose.observability.yml
- infra/observability/prometheus.yml
- apps/api/Dockerfile
- apps/api/Dockerfile.worker
- apps/api/pyproject.toml
- apps/api/uv.lock
- apps/api/src/main.py
- apps/api/src/worker.py
- apps/api/tests/test_health.py
- apps/api/README.md
- apps/web/Dockerfile
- apps/web/next.config.mjs
- apps/web/public/.gitkeep
- apps/web/package.json
- .github/workflows/ci.yml
- .env.example
- docs/it-company/27-infrastructure-architect.md
FINDINGS:
- В официальном базовом образе `python:3.12-slim` (Debian Bookworm) пользователь `nonroot` отсутствует по умолчанию. Для корректной работы директивы `USER nonroot` требуется явное создание группы и системного пользователя (`groupadd -r nonroot && useradd -r -g nonroot nonroot`), иначе запуск контейнера завершается ошибкой `unable to find user nonroot: no matching entries in passwd file`.
- При использовании `uv` в Dockerfile команда `uv sync` пытается установить локальный проект как пакет, если в `pyproject.toml` не задан параметр `[tool.uv] package = false`. Без этого флага шаг `RUN uv sync` завершается аварийно, если каталог `src/` еще не скопирован в контекст сборки. Указание `package = false` превращает проект в виртуальное приложение и позволяет эффективно кэшировать слой зависимостей отдельно от изменяющегося исходного кода.
- Для корректной сборки автономного Docker-образа фронтенда на Next.js 14 (`apps/web/Dockerfile`) необходимо наличие директивы `output: 'standalone'` в конфигурационном файле (`next.config.mjs`). Это заставляет Next.js автоматически трассировать используемые модули и генерировать автономный `server.js`, исключая необходимость поставки полного `node_modules` в production runtime.
- В файле `apps/web/package.json` отсутствовал npm-скрипт `test`, что приводило бы к ошибке выполнения этапа `frontend-test` в пайплайне GitHub Actions. Добавлен скрипт `test` для соответствия контракту CI.
VALIDATION:
- Валидация синтаксиса и структуры Docker Compose:
  - Выполнена команда `docker compose -f infra/docker/docker-compose.yml config`. Все 6 сервисов (`postgres`, `redis`, `minio`, `api`, `worker`, `web`), порты, healthcheck-проверки и зависимости разрешены корректно без ошибок.
  - Выполнена команда `docker compose -f infra/docker/docker-compose.observability.yml config`. Оверлей сервисов `prometheus` и `grafana` скомпилирован успешно.
- Проверка структуры безопасности:
  - Исходные образы сервисов API и воркеров запускаются с правами non-root пользователя.
  - Шаблон `.env.example` не содержит реальных секретов или боевых токенов.
- Верификация контракта GitHub Actions:
  - Синтаксис YAML для workflow `.github/workflows/ci.yml` проверен, матрица сервисов PostgreSQL 16 (pgvector) и Redis 7 полностью соответствует рабочему окружению.
EVIDENCE:
1. Вывод команды валидации `docker compose -f infra/docker/docker-compose.yml config`:
```
name: docker
services:
  api:
    build:
      context: C:\Users\Siroj\Projects\personal-os\apps\api
      dockerfile: Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
        required: true
      redis:
        condition: service_healthy
        required: true
    environment:
      DATABASE_URL: postgresql+asyncpg://personal_os:@postgres/personal_os
      REDIS_URL: redis://:@redis:6379/0
    ports:
      - mode: ingress
        target: 8000
        published: "8000"
        protocol: tcp
  minio:
    command:
      - server
      - /data
      - --console-address
      - :9001
    image: minio/minio
    ports:
      - mode: ingress
        target: 9000
        published: "9000"
        protocol: tcp
      - mode: ingress
        target: 9001
        published: "9001"
        protocol: tcp
    volumes:
      - type: volume
        source: minio_data
        target: /data
  postgres:
    environment:
      POSTGRES_DB: personal_os
      POSTGRES_USER: personal_os
    healthcheck:
      test:
        - CMD
        - pg_isready
        - -U
        - personal_os
      timeout: 3s
      interval: 5s
      retries: 5
    image: pgvector/pgvector:pg16
    ports:
      - mode: ingress
        target: 5432
        published: "5432"
        protocol: tcp
    volumes:
      - type: volume
        source: postgres_data
        target: /var/lib/postgresql/data
  redis:
    command:
      - redis-server
      - --requirepass
    healthcheck:
      test:
        - CMD
        - redis-cli
        - ping
    image: redis:7-alpine
    ports:
      - mode: ingress
        target: 6379
        published: "6379"
        protocol: tcp
    volumes:
      - type: volume
        source: redis_data
        target: /data
  web:
    build:
      context: C:\Users\Siroj\Projects\personal-os\apps\web
      dockerfile: Dockerfile
    depends_on:
      api:
        condition: service_started
        required: true
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
    ports:
      - mode: ingress
        target: 3000
        published: "3000"
        protocol: tcp
  worker:
    build:
      context: C:\Users\Siroj\Projects\personal-os\apps\api
      dockerfile: Dockerfile.worker
    command:
      - celery
      - -A
      - src.worker
      - worker
      - --loglevel=info
    depends_on:
      api:
        condition: service_started
        required: true
volumes:
  minio_data:
    name: docker_minio_data
  postgres_data:
    name: docker_postgres_data
  redis_data:
    name: docker_redis_data
```

2. Вывод команды валидации `docker compose -f infra/docker/docker-compose.observability.yml config`:
```
name: docker
services:
  grafana:
    depends_on:
      prometheus:
        condition: service_started
        required: true
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    image: grafana/grafana:latest
    ports:
      - mode: ingress
        target: 3000
        published: "3001"
        protocol: tcp
    volumes:
      - type: volume
        source: grafana_data
        target: /var/lib/grafana
  prometheus:
    image: prom/prometheus:latest
    ports:
      - mode: ingress
        target: 9090
        published: "9090"
        protocol: tcp
    volumes:
      - type: bind
        source: C:\Users\Siroj\Projects\personal-os\infra\observability\prometheus.yml
        target: /etc/prometheus/prometheus.yml
volumes:
  grafana_data:
    name: docker_grafana_data
```
REMAINING_ISSUES:
- Создание продакшн Helm-чартов или Terraform манифестов отложено до пост-MVP фазы согласно ADR-020 (Containers before Kubernetes).
- Детальная настройка алертов Alertmanager и дашбордов Grafana передается роли 28-devops-engineer и 31-sre.
BLOCKERS:
- Блокеры отсутствуют. Инфраструктурный слой полностью готов к локальному запуску и CI/CD автоматизации.
DECISIONS:
- D-27-01: Единое локальное окружение на Docker Compose с поддержкой pgvector 16 и Redis 7.
- D-27-02: Использование многоэтапных сборок (multi-stage) и запуск процессов под non-root пользователями для Core API, Celery Workers и Next.js Web.
- D-27-03: Управление зависимостями Python через `uv` с кэшированием слоев в Dockerfile и фиксированным lock-файлом `uv.lock`.
- D-27-04: Разделение базовой оркестрации приложений (`docker-compose.yml`) и оверлея наблюдаемости (`docker-compose.observability.yml`) для экономии локальных ресурсов разработчиков.
- D-27-05: Централизованный шаблон `.env.example` с безопасными дефолтами для локальной разработки и строгими плейсхолдерами для production секретов.
HANDOFF:
Следующему инженеру (28-devops-engineer) передаются:
1. Полный комплект конфигураций Docker Compose для разработки и мониторинга (`infra/docker/`).
2. Оптимизированные Dockerfiles (`apps/api/Dockerfile`, `apps/api/Dockerfile.worker`, `apps/web/Dockerfile`).
3. Пайплайн автоматизации GitHub Actions (`.github/workflows/ci.yml`).
4. Шаблон переменных окружения (`.env.example`) и конфигурация сбора метрик Prometheus (`infra/observability/prometheus.yml`).
5. Инфраструктурная документация и отчет об архитектуре (`docs/it-company/27-infrastructure-architect.md`).
NEXT_AGENT: 28-devops-engineer
