from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.users.user import User


class Client(User):
  __tablename__ = "clients"

  user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)

  projects: Mapped[list["Project"]] = relationship(
    back_populates="client",
    cascade="all, delete-orphan",
  )

  __mapper_args__ = {
    "polymorphic_identity": "client",
  }
