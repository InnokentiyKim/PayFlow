FROM python:3.13-slim AS builder

WORKDIR build/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv venv /build/.venv && \
    VIRTUAL_ENV=/build/.venv uv sync --frozen --no-dev --no-install-project


FROM python:3.13-slim

WORKDIR app/

COPY --from=builder /build/.venv /app/.venv

COPY app/ ./app/
COPY migrations/ ./migrations/

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["python", "-m", "app.main"]
