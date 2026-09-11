FROM python:3.12-slim
WORKDIR /app
RUN groupadd -r nonroot && useradd -r -g nonroot nonroot
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY src/ ./src/
USER nonroot
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
