
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImageFormat(str, enum.Enum):
    png = "png"
    jpeg = "jpeg"
    webp = "webp"
    gif = "gif"
    bmp = "bmp"
    tiff = "tiff"


class Image(Base):
  __tablename__ = "images"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  filename: Mapped[str] = mapped_column(String(255), nullable=False)

  width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
  height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

  image_type: Mapped[Optional[ImageFormat]] = mapped_column(
    SQLEnum(ImageFormat, native_enum=False),
    nullable=True,
  )

  minio_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
  minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False)

  content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
  qdrant_collection: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
  qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
  )
