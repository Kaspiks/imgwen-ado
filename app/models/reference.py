
from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReferenceStyle(Base):
  __tablename__ = "references"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  style_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)

  name: Mapped[str] = mapped_column(String(255), nullable=False)
  category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
  description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

  tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(128)), nullable=True)
  visual_tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(256)), nullable=True)

  source: Mapped[str] = mapped_column(String(50))

  session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
  image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), nullable=False)

  session: Mapped["ChatSession"] = relationship(back_populates="reference_styles")
  image: Mapped["Image"] = relationship()
