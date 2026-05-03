#!/bin/bash

set -e  # exit immediately if any command fails

RUN_PORT="${PORT:-8000}"

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI server..."
exec gunicorn src.main:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind "[::]:$RUN_PORT" \
    --proxy-headers \
    --forwarded-allow-ips="*"