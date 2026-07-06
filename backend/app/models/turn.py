from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
import uuid as _uuid


class Turn(UUIDMixin, Base):
    __tablename__ = "turns"

    session_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False
    )
    speaker_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("speakers.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int] = mapped_column(nullable=False)
    end_ms: Mapped[int] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    turn_index: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="turn_confidence_check"),
    )

    session: Mapped["Session"] = relationship(back_populates="turns")
    speaker: Mapped["Speaker"] = relationship(back_populates="turns")
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="turn")
    acoustic_labels: Mapped[list["AcousticLabel"]] = relationship(back_populates="turn")
    audio_events: Mapped[list["AudioEvent"]] = relationship(back_populates="turn")
