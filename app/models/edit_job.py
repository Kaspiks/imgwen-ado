from __future__ import annotations

import enum

from sqlalchemy import Enum as SQLEnum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EditJobStatus(str, enum.Enum):
  pending = "pending"
  running = "running"
  done = "done"
  failed = "failed"


class EditJob(Base):
  __tablename__ = "edit_jobs"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  status: Mapped[EditJobStatus] = mapped_column(
    SQLEnum(EditJobStatus, native_enum=False),
    nullable=False,
    default=EditJobStatus.pending,
    server_default=text("'pending'"),
  )

  session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)

  session: Mapped["ChatSession"] = relationship(back_populates="jobs")

  variations: Mapped[list["GeneratedVariation"]] = relationship(
    back_populates="job",
    cascade="all, delete-orphan",
  )
