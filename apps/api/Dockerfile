FROM python:3.12-slim
WORKDIR /app
RUN groupadd -r nonroot && useradd -r -g nonroot nonroot
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/models/.hf
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY docker-entrypoint.sh ./
# Attachments are written to /app/data/uploads (relative to WORKDIR): it must be
# writable by the non-root user. Mount a volume at /app/data to keep the files.
# /app/models: speech model for voice messages (own volume, kept out of the /app/data backups).
RUN chmod +x docker-entrypoint.sh \
    && mkdir -p /app/data/uploads /app/models \
    && chown -R nonroot:nonroot /app/data /app/models
VOLUME ["/app/data"]
USER nonroot
EXPOSE 8000
# PORT is provided by PaaS hosts (Render, Railway...); 8000 otherwise.
# RUN_MIGRATIONS=1 applies `alembic upgrade head` before start (single-instance hosts).
CMD ["./docker-entrypoint.sh"]
