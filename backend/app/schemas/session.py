from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    title: str = "Untitled Session"
    language: str = "en"


class SessionResponse(BaseModel):
    id: UUID
    title: str
    language: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    turn_count: int = 0
    duration_ms: int = 0


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
