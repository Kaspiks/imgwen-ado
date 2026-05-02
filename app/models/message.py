from sqlalchemy import ForeignKey, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Message(Base):
  __tablename__ = "messages"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)

  role: Mapped[str] = mapped_column(String(20))
  content: Mapped[str] = mapped_column(Text)

  session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
  session: Mapped["ChatSession"] = relationship(back_populates="messages")