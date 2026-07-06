from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
import uuid as _uuid


class AcousticLabel(UUIDMixin, Base):
    __tablename__ = "acoustic_labels"

    turn_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("turns.id"), nullable=False
    )
    head: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    extra_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="acoustic_label_confidence_check"
        ),
    )

    turn: Mapped["Turn"] = relationship(back_populates="acoustic_labels")
