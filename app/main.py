from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.routers import edit_flow, project, workflow


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title="imgwen-ado", lifespan=lifespan)
app.include_router(workflow.router, prefix="/api")
app.include_router(edit_flow.router, prefix="/api")
app.include_router(project.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def health_api() -> dict[str, str]:
    """Same as /health; lives under /api so the SPA can probe through a single /api prefix."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
