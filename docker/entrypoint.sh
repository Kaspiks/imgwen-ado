#!/bin/sh
set -e
python -m app.init_db
python -m app.seed_references
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
