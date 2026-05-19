from app.database import Base, engine

import app.models  # noqa: F401

from sqlalchemy import text


def _migrate() -> None:
    """Lightweight column adds for existing Postgres volumes (no Alembic)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE edit_flow_messages "
                "ADD COLUMN IF NOT EXISTS reference_urls JSON NOT NULL DEFAULT '[]'"
            )
        )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate()


if __name__ == "__main__":
    main()
