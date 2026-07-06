from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
import uuid as _uuid


class Embedding(UUIDMixin, Base):
    __tablename__ = "embeddings"

    session_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False
    )
    turn_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("turns.id"), nullable=False
    )
    encoder_version: Mapped[str] = mapped_column(String(64), nullable=False)
    vector_id: Mapped[_uuid.UUID] = mapped_column(nullable=False)
    dims: Mapped[int] = mapped_column(nullable=False)

    session: Mapped["Session"] = relationship(back_populates="embeddings")
    turn: Mapped["Turn"] = relationship(back_populates="embeddings")
