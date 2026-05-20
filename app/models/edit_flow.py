from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, JSON, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EditFlowPhase(str, enum.Enum):
    chatting = "chatting"
    awaiting_references = "awaiting_references"
    edit_completed = "edit_completed"


class EditFlowSession(Base):
    __tablename__ = "edit_flow_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    base_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[EditFlowPhase] = mapped_column(
        SQLEnum(EditFlowPhase, native_enum=False),
        nullable=False,
        default=EditFlowPhase.chatting,
        server_default=text("'chatting'"),
    )

    reference_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    last_edit_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["EditFlowMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class EditFlowMessage(Base):
    __tablename__ = "edit_flow_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reference_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default=text("'[]'"))

    session_id: Mapped[int] = mapped_column(
        ForeignKey("edit_flow_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session: Mapped["EditFlowSession"] = relationship(back_populates="messages")
