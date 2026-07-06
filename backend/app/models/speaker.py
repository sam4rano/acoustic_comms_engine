from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
import uuid as _uuid


class Speaker(UUIDMixin, Base):
    __tablename__ = "speakers"

    session_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_id: Mapped[_uuid.UUID | None] = mapped_column(nullable=True)

    session: Mapped["Session"] = relationship(back_populates="speakers")
    turns: Mapped[list["Turn"]] = relationship(back_populates="speaker")
