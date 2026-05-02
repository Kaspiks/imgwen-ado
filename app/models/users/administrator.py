from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.users.user import User


class Administrator(User):
  __tablename__ = "administrators"

  user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)

  __mapper_args__ = {
    "polymorphic_identity": "administrator",
  }
