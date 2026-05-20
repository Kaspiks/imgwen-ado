#!/bin/sh
set -e
python -m app.init_db
python -m app.seed_references

UVICORN_ARGS="app.main:app --host 0.0.0.0 --port 8000"

if [ "${DEBUGPY_ENABLE:-0}" = "1" ]; then
  DEBUGPY_PORT="${DEBUGPY_PORT:-5678}"
  DEBUGPY_FLAGS="--listen 0.0.0.0:${DEBUGPY_PORT}"
  if [ "${DEBUGPY_WAIT:-0}" = "1" ]; then
    DEBUGPY_FLAGS="${DEBUGPY_FLAGS} --wait-for-client"
  fi
  echo "[entrypoint] debugpy listening on 0.0.0.0:${DEBUGPY_PORT} (attach from host port ${DEBUGPY_PORT})"
  exec python -m debugpy ${DEBUGPY_FLAGS} -m uvicorn ${UVICORN_ARGS}
fi

exec uvicorn ${UVICORN_ARGS}
