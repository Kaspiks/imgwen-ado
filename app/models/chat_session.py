
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatSessionStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    closed = "closed"


class ChatSession(Base):
  __tablename__ = "chat_sessions"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  status: Mapped[ChatSessionStatus] = mapped_column(
    SQLEnum(ChatSessionStatus, native_enum=False),
    nullable=False,
    default=ChatSessionStatus.active,
    server_default=text("'active'"),
  )

  title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
  description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  edit_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
  )

  project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
  original_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("images.id"), nullable=True)
  edited_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("images.id"), nullable=True)

  project: Mapped["Project"] = relationship(back_populates="sessions")

  messages: Mapped[list["Message"]] = relationship(
    back_populates="session",
    cascade="all, delete-orphan",
  )

  reference_styles: Mapped[list["ReferenceStyle"]] = relationship(
    back_populates="session",
    cascade="all, delete-orphan",
  )

  jobs: Mapped[list["EditJob"]] = relationship(
    back_populates="session",
    cascade="all, delete-orphan",
  )
