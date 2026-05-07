from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GeneratedVariation(Base):
  __tablename__ = "generated_variations"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  job_id: Mapped[int] = mapped_column(ForeignKey("edit_jobs.id"))
  image_id: Mapped[int] = mapped_column(ForeignKey("images.id"))

  score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

  job: Mapped["EditJob"] = relationship(back_populates="variations")
  image: Mapped["Image"] = relationship()