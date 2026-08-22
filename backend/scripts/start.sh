#!/bin/sh
set -eu

alembic upgrade head

if [ "${DEMO_DATA_ENABLED:-false}" = "true" ]; then
  python -m scripts.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
