# ── Stage 1: build frontend ──────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── Stage 2: Python runtime ─────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY packages/ packages/
RUN pip install --no-cache-dir -e .

COPY api/ api/
COPY servers/ servers/
COPY evals/ evals/
COPY tests/ tests/

COPY --from=frontend-build /app/web/dist /app/web/dist

RUN mkdir -p /app/data

ENV PYTHONPATH=/app/packages/core:/app
ENV FINANCE_DB_PATH=/app/data/finance.db
ENV FINANCE_QUOTE_BACKEND=mock
ENV REQUIRE_AUTH=false
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
