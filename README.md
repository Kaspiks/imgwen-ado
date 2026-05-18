# imgwen-ado

## Frontend (Vite + React)

```bash
cd frontend && npm install && npm run dev
```

Dev server (default Vite port): `http://127.0.0.1:5173`.

### Static UI in Docker (nginx on port 3000)

```bash
docker compose up --build web
```

Open `http://127.0.0.1:3000`. Combine with the API: `docker compose up --build web api` (plus `postgres` if the API should run in Compose).

## Local (Postgres etc. in Docker, app on host)

```bash
docker compose up -d postgres redis qdrant minio
pip install -e .
python -m app.init_db
uvicorn app.main:app --reload
```

`DATABASE_URL` default matches Compose’s published Postgres: `postgresql+psycopg://app:app@127.0.0.1:5432/app_db`. Override in `.env` if needed.

## Full stack in Docker

```bash
docker compose up --build
```

API on `http://127.0.0.1:8000`. The `api` service uses host `postgres` in `DATABASE_URL` (see `docker-compose.yml`).
