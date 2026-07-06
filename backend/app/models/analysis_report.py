from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UUIDMixin
from datetime import datetime
import uuid as _uuid


class AnalysisReport(UUIDMixin, Base):
    __tablename__ = "analysis_reports"

    session_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    coaching: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_trace: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    degradation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    session: Mapped["Session"] = relationship(back_populates="analysis_reports")
