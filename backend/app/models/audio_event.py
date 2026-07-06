from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
from app.models.enums import AudioEventType
import uuid as _uuid


class AudioEvent(UUIDMixin, Base):
    __tablename__ = "audio_events"

    session_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False
    )
    turn_id: Mapped[_uuid.UUID | None] = mapped_column(
        ForeignKey("turns.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_ms: Mapped[int] = mapped_column(nullable=False)
    end_ms: Mapped[int] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="audio_event_confidence_check"
        ),
    )

    session: Mapped["Session"] = relationship(back_populates="audio_events")
    turn: Mapped["Turn | None"] = relationship(back_populates="audio_events")
