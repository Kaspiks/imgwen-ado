from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
  __tablename__ = "users"

  user_id: Mapped[str] = mapped_column(String(36), primary_key=True)

  username: Mapped[str] = mapped_column(String(255), nullable=False)

  email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

  password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

  user_type: Mapped[str] = mapped_column(String(50))

  __mapper_args__ = {
    "polymorphic_on": user_type,
  }
