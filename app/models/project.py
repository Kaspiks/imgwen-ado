
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.users import Client


class ProjectStatus(str, enum.Enum):
  draft = "draft"
  active = "active"
  archived = "archived"


class Project(Base):
  __tablename__ = "projects"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  project_name: Mapped[str] = mapped_column(String(255), nullable=False)
  thumbnail_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

  status: Mapped[ProjectStatus] = mapped_column(
    SQLEnum(ProjectStatus, native_enum=False),
    nullable=False,
    default=ProjectStatus.draft,
    server_default=text("'draft'"),
  )

  tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(128)), nullable=True)
  export_readiness: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")

  creation_date: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
  )

  last_interaction_time: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
  )

  total_edits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

  user_id: Mapped[str] = mapped_column(ForeignKey("clients.user_id"), nullable=False)

  client: Mapped[Client] = relationship(back_populates="projects")

  sessions: Mapped[list["ChatSession"]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
  )
