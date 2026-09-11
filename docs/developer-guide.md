# Руководство разработчика Personal OS

## Локальная разработка

### 1. Бэкенд (Python 3.12 + FastAPI):
```bash
cd apps/api
pip install uv
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --port 8000
```

### 2. Фронтенд (Next.js 14):
```bash
cd apps/web
npm install
npm run dev
```

### 3. Запуск тестов:
```bash
# Бэкенд тесты
cd apps/api && python -m pytest tests/ -v

# Фронтенд тесты
cd apps/web && npm test

# Проверка типов
cd apps/web && npm run typecheck
```
