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

        conn.execute(
            text(
                "ALTER TABLE chat_sessions "
                "ADD COLUMN IF NOT EXISTS edit_sequence_number INTEGER NOT NULL DEFAULT 0"
            )
        )
        
        conn.execute(
            text(
                "ALTER TABLE chat_sessions "
                "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            )
        )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate()


if __name__ == "__main__":
    main()
