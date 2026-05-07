#!/bin/sh
set -e
python -m app.init_db
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
