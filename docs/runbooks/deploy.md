# Deploy Runbook

## Запуск проекта (dev)
1. `cp .env.example .env` и заполнить секреты
2. `docker compose -f infra/docker/docker-compose.yml up -d`
3. `docker compose exec api uv run alembic upgrade head`
4. Открыть http://localhost:3000

### Запуск с дополнительными сервисами (Celery Beat & Flower)
Для запуска планировщика задач и мониторинга очередей используйте оверлей воркеров:
```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.worker.yml up -d
```
Flower UI доступен по адресу: http://localhost:5555

### Запуск с мониторингом (Prometheus & Grafana)
```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.observability.yml up -d
```
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (дефолтный логин/пароль: `admin` / `admin`)

## Откат (роллбек)
1. `docker compose pull` (предыдущая версия образа)
2. `docker compose up -d`
3. Если необходимо: `alembic downgrade -1`

### Экстренный откат базы данных
В случае неудачной миграции или порчи данных:
```bash
# Проверка текущей ревизии базы данных
docker compose exec api uv run alembic current

# Откат на одну ревизию назад
docker compose exec api uv run alembic downgrade -1

# Откат на конкретную стабильную ревизию
docker compose exec api uv run alembic downgrade <revision_id>
```

## Health checks
- API: `curl http://localhost:8000/health` (или `curl http://localhost:8000/healthz`)
- WS: `wscat -c ws://localhost:8000/v1/ws`
- DB: `docker compose exec postgres pg_isready`
- Redis: `docker compose exec redis redis-cli ping`
- MinIO: `curl http://localhost:9000/minio/health/live`

## CI/CD Деплоймент (Production/Staging)
Пайплайн Continuous Deployment запускается автоматически по триггеру GitHub Actions (`.github/workflows/cd.yml`):
- При пуше в ветку `master`
- При создании тегов релиза `v*` (например, `v1.0.0`)

### Схема обновления контейнеров на сервере:
1. GitHub Actions собирает Docker-образы `api` и `web` с тегом `${{ github.sha }}`.
2. Образы пушатся в GitHub Container Registry (`ghcr.io/owner/personal-os/{api,web}`).
3. По SSH выполняется обновление рабочей директории:
   ```bash
   cd /opt/personal-os
   export IMAGE_TAG=${GITHUB_SHA}
   docker compose pull
   docker compose up -d --no-deps api web
   docker compose exec api uv run alembic upgrade head
   ```
