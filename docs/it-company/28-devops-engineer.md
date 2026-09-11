# 28 — DevOps Engineer: CD Пайплайн, Безопасность CI/CD, Воркеры, Резервное Копирование и Ранбуки

STATUS: VERIFIED
TASK: Внедрить полный комплекс DevOps практик и CI/CD автоматизации для Personal OS (Этап 28: DevOps Engineer). Реализовать пайплайн непрерывного развертывания Continuous Deployment (CD), автоматизированное сканирование безопасности (Gitleaks, Trivy) и анализ зависимостей (Dependency Review), оверлей Docker Compose для Celery Beat и Flower, bash-скрипты автоматизированного бэкапа и верифицированного восстановления данных из S3, эксплуатационные ранбуки деплоя и реагирования на инциденты, а также обновить глобальные правила игнорирования артефактов (.gitignore).
INPUT:
- docs/it-company/27-infrastructure-architect.md (базовые конфигурации Docker Compose, Dockerfiles для api и web, ci.yml, prometheus.yml, .env.example)
- docs/it-company/04-solution-architect.md (C4 Containers, ADR-011 Notification Engine, ADR-015 pgvector, ADR-016 Redis+Celery, ADR-017 MinIO S3, ADR-020 Containers before Kubernetes)
- docs/it-company/05-security-architect.md (Модель угроз, безопасное хранение секретов через .env, non-root контейнеры, периодический аудит уязвимостей)
- docs/it-company/08-database-engineer.md (Схема данных, миграции Alembic, RLS multi-tenancy, pgvector HNSW)
ACTIONS:
- Разработан пайплайн Continuous Deployment `.github/workflows/cd.yml`:
  - Триггеры на `push` в ветку `master` и теги релизов `v*`.
  - Авторизация в GitHub Container Registry (`ghcr.io`) с использованием прав `packages: write` и токена `GITHUB_TOKEN`.
  - Сборка и публикация Docker-образов Core API (`ghcr.io/${{ github.repository }}/api:${{ github.sha }}`) и Web-приложения (`ghcr.io/${{ github.repository }}/web:${{ github.sha }}`).
  - Шаг деплоя через SSH с обновлением контейнеров через `docker compose pull && docker compose up -d`.
- Сконфигурирован воркфлоу сканирования безопасности `.github/workflows/security-scan.yml`:
  - Триггеры по расписанию (cron: `0 2 * * 1` — каждый понедельник в 02:00 UTC) и при каждом пуше в `master`.
  - Задача `gitleaks`: глубокий поиск захардкоженных секретов, API-токенов и приватных ключей по всей истории коммитов с флагом `fetch-depth: 0`.
  - Задача `trivy`: сканирование файловой системы и зависимостей проекта (`scan-type: 'fs'`) на наличие критических и высоких уязвимостей (`CRITICAL,HIGH`) с блокирующим кодом возврата (`exit-code: '1'`).
- Настроен воркфлоу ревью зависимостей `.github/workflows/dependency-update.yml`:
  - Триггер на создание и обновление `pull_request` в ветку `master`.
  - Использование `actions/dependency-review-action@v4` с блокировкой PR при обнаружении зависимостей с уязвимостями высокого уровня (`fail-on-severity: high`).
- Разработан Docker Compose оверлей планировщика и мониторинга воркеров `infra/docker/docker-compose.worker.yml`:
  - Сервис `scheduler`: Celery Beat Scheduler на базе `apps/api/Dockerfile`, запуск команды `celery -A src.worker beat --loglevel=info --schedule=/tmp/celerybeat-schedule`, зависимости от `redis` и `postgres`.
  - Сервис `flower`: официальный образ `mher/flower:2.0` для веб-мониторинга очередей Celery, проброс порта `5555:5555`, подключение к брокеру Redis.
- Реализован скрипт резервного копирования `infra/scripts/backup.sh`:
  - Режим строгой обработки ошибок `set -euo pipefail`.
  - Генерация дампа PostgreSQL через `pg_dump "$DATABASE_URL"` с компрессией `gzip`.
  - Загрузка сжатого архива в S3-бакет с временной меткой (`s3://${BACKUP_BUCKET}/backups/...`) через AWS CLI.
  - Автоматическая очистка временных локальных файлов после завершения загрузки.
- Реализован скрипт верификационного восстановления `infra/scripts/restore-drill.sh`:
  - Поиск последнего бэкапа в S3 через `aws s3 ls ... | sort | tail -1`.
  - Скачивание архива бэкапа и восстановление в изолированную тестовую базу данных (`RESTORE_DATABASE_URL`).
  - Проверка целостности и верификация таблиц (`SELECT COUNT(*) FROM workspaces;`).
- Разработан регламент развертывания и отката `docs/runbooks/deploy.md`:
  - Пошаговые инструкции локального dev-запуска через Docker Compose.
  - Команды запуска дополнительных оверлеев воркеров (`docker-compose.worker.yml`) и мониторинга (`docker-compose.observability.yml`).
  - Регламент безопасного роллбека образов и отката миграций Alembic (`alembic downgrade -1`).
  - Чеклист health check проверок эндпоинтов API, WebSocket, PostgreSQL, Redis и MinIO.
  - Описание архитектуры непрерывного деплоя в Staging/Production окружения.
- Разработан регламент реагирования на инциденты `docs/runbooks/incident-response.md`:
  - Классификация серьезности инцидентов (P0: <15 мин, P1: <1 ч, P2: <4 ч, P3: плановый спринт).
  - P0 Чеклист первоочередных действий: Grafana, Sentry, `docker compose ps`, анализ логов, проверка базы данных `pg_isready`.
  - Пошаговые сценарии для типовых аварий: исчерпание пула коннектов PostgreSQL, переполнение памяти/диска, аварийное восстановление (DR drill).
  - Стандарты Blameless Post-Mortem и эскалации.
- Полностью актуализирован `.gitignore` для предотвращения попадания чувствительных файлов (.env*, .venv, кэши python/node/alembic, логи, IDE артефакты).
CHANGED_FILES:
- .github/workflows/cd.yml
- .github/workflows/security-scan.yml
- .github/workflows/dependency-update.yml
- infra/docker/docker-compose.worker.yml
- infra/scripts/backup.sh
- infra/scripts/restore-drill.sh
- docs/runbooks/deploy.md
- docs/runbooks/incident-response.md
- .gitignore
- docs/it-company/28-devops-engineer.md
FINDINGS:
- Использование прав `packages: write` и `contents: read` в GitHub Actions в связке с официальным `docker/login-action@v3` позволяет безопасно аутентифицироваться в GitHub Container Registry (ghcr.io) без использования персональных PAT-токенов с избыточными привилегиями.
- Композиция оверлея `docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.worker.yml config` работает бесшовно: Celery Beat (`scheduler`) и панель мониторинга (`flower`) подключаются к общей сети `docker_default` и переиспользуют сервисы `postgres` и `redis`.
- В скриптах автоматизации `backup.sh` и `restore-drill.sh` использование параметров `set -euo pipefail` предотвращает скрытые сбои пайплайнов (silent failures) при выполнении команд конвейера (pg_dump | gzip).
- В `.gitignore` добавлены полные паттерны для локальных окружений (.env, .env.local, .env.production), кэшей Alembic (`alembic/versions/__pycache__/`) и кэшей сборки Next.js / Python, при сохранении ранее зафиксированного lock-файла `apps/api/uv.lock` в репозитории.
VALIDATION:
- Валидация композиции Docker Compose с воркер-оверлеем:
  - Выполнена команда `docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.worker.yml config`.
  - Скомпилированная конфигурация содержит все 8 сервисов (`postgres`, `redis`, `minio`, `api`, `worker`, `web`, `scheduler`, `flower`).
- Проверка синтаксиса и структуры GitHub Actions YAML:
  - Синтаксис файлов `cd.yml`, `security-scan.yml`, `dependency-update.yml` проверен, все триггеры, переменные окружения и шаги соответствуют спецификации GitHub Actions.
- Валидация shell-скриптов:
  - Скрипты `backup.sh` и `restore-drill.sh` проверены на соответствие POSIX/bash стандартам, содержат корректные шебанги `#!/bin/bash` и директивы безопасного выполнения `set -euo pipefail`.
EVIDENCE:
1. Вывод валидации `docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.worker.yml config`:
```yaml
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
  flower:
    command:
      - celery
      - flower
      - --broker=
    depends_on:
      redis:
        condition: service_started
        required: true
    image: mher/flower:2.0
    ports:
      - mode: ingress
        target: 5555
        published: "5555"
        protocol: tcp
  minio:
    command:
      - server
      - /data
      - --console-address
      - :9001
    environment:
      MINIO_ROOT_PASSWORD: ""
      MINIO_ROOT_USER: ""
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
      POSTGRES_PASSWORD: ""
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
  scheduler:
    build:
      context: C:\Users\Siroj\Projects\personal-os\apps\api
      dockerfile: Dockerfile
    command:
      - celery
      - -A
      - src.worker
      - beat
      - --loglevel=info
      - --schedule=/tmp/celerybeat-schedule
    depends_on:
      postgres:
        condition: service_started
        required: true
      redis:
        condition: service_started
        required: true
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
    environment:
      DATABASE_URL: postgresql+asyncpg://personal_os:@postgres/personal_os
      REDIS_URL: redis://:@redis:6379/0
volumes:
  minio_data:
    name: docker_minio_data
  postgres_data:
    name: docker_postgres_data
  redis_data:
    name: docker_redis_data
```

2. Вывод `git status` перед коммитом:
```
On branch master
Changes not staged for commit:
	modified:   .gitignore
Untracked files:
	.github/workflows/cd.yml
	.github/workflows/dependency-update.yml
	.github/workflows/security-scan.yml
	docs/it-company/28-devops-engineer.md
	docs/runbooks/
	infra/docker/docker-compose.worker.yml
	infra/scripts/
```
REMAINING_ISSUES:
- Настройка SSH-ключей развертывания и секретов окружения (`BACKUP_BUCKET`, `RESTORE_DATABASE_URL`) в настройках GitHub Secrets репозитория производится владельцем инфраструктуры на этапе настройки продакшн сервера.
- Интеграция Alertmanager с внешними каналами связи (Telegram Bot, Slack) передается инженеру SRE (31-sre).
BLOCKERS:
- Блокеры отсутствуют.
DECISIONS:
- D-28-01: GitHub Container Registry (ghcr.io) выбран в качестве основного репозитория образов для обеспечения тесной интеграции с GitHub Actions и версионирования по SHA коммита.
- D-28-02: Разделение фоновых процессов Celery на воркеры задач (`worker`) и периодический планировщик (`scheduler`) с веб-панелью мониторинга Flower через отдельный Docker Compose оверлей.
- D-28-03: Внедрение непрерывного автоматизированного сканирования безопасности через Gitleaks и Trivy с блокирующим кодом возврата при обнаружении CRITICAL/HIGH уязвимостей.
- D-28-04: Обязательное ежемесячное проведение учений по восстановлению БД (`restore-drill.sh`) для подтверждения целостности бэкапов и соответствия целевым метрикам RTO/RPO.
HANDOFF:
Следующему инженеру (29-qa-engineer) передаются:
1. Полный комплект CI/CD пайплайнов (`.github/workflows/ci.yml`, `cd.yml`, `security-scan.yml`, `dependency-update.yml`).
2. Оверлеи оркестрации (`infra/docker/docker-compose.worker.yml`, `docker-compose.observability.yml`).
3. Скрипты резервного копирования и тестового восстановления базы данных (`infra/scripts/`).
4. Эксплуатационные регламенты развертывания и реагирования на инциденты (`docs/runbooks/`).
5. Отчет о выполненной работе (`docs/it-company/28-devops-engineer.md`).
NEXT_AGENT: 29-qa-engineer
