# API server (dashboard backend). Build the web UI separately or serve static files with nginx.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

ENV PYTHONUNBUFFERED=1
ENV FINANCE_DB_PATH=/data/finance.db
ENV FINANCE_QUOTE_BACKEND=mock

RUN pip install --no-cache-dir pip -U

COPY pyproject.toml setup.py README.md ./
COPY packages/core/finance_core ./packages/core/finance_core/
COPY api ./api/

RUN pip install --no-cache-dir -e .

EXPOSE 8001

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
