FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev extras)
RUN uv sync --frozen --no-dev

# Copy application source
COPY backend/ backend/
COPY pipeline/ pipeline/
COPY knowledge_base/ knowledge_base/
COPY alembic/ alembic/
COPY alembic.ini ./

ENV PYTHONUNBUFFERED=1

# Cloud Run sets PORT; default to 8080
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
