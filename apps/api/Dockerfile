FROM python:3.12-slim
WORKDIR /app
RUN groupadd -r nonroot && useradd -r -g nonroot nonroot
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
USER nonroot
EXPOSE 8000
# PORT is provided by PaaS hosts (Render, Railway...); 8000 otherwise.
# RUN_MIGRATIONS=1 applies `alembic upgrade head` before start (single-instance hosts).
CMD ["./docker-entrypoint.sh"]
