from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime
from typing import Optional


@dataclass
class MemoryDocument:
    id: UUID
    title: str
    content: str
    user_id: UUID
    created_at: datetime
    score: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryQuery:
    text: str
    user_id: UUID
    top_k: int = 10
    threshold: float = 0.6
    head: Optional[str] = None


@dataclass
class MemoryResult:
    documents: list[MemoryDocument]
    query: MemoryQuery
    retrieval_time_ms: float
    source: str


@dataclass
class SessionSummary:
    session_id: UUID
    user_id: UUID
    started_at: datetime
    duration_s: int
    turn_count: int
    language: str
    overall_score: Optional[float] = None
    labels: list[str] = field(default_factory=list)


@dataclass
class TurnSummary:
    turn_id: UUID
    speaker_label: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    acoustic_labels: dict[str, str] = field(default_factory=dict)


@dataclass
class EmbeddingMatch:
    embedding_id: UUID
    turn_id: UUID
    score: float
    head: str


@dataclass
class RetrievalBundle:
    core_turns: list[TurnSummary] = field(default_factory=list)
    relevant_turns: list[TurnSummary] = field(default_factory=list)
    acoustic_neighbors: list[EmbeddingMatch] = field(default_factory=list)
    documents: list[MemoryDocument] = field(default_factory=list)
    prior_sessions: list[SessionSummary] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
