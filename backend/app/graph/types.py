from dataclasses import dataclass, field
from uuid import UUID
from typing import Literal, Optional


@dataclass
class SpeakerNode:
    id: UUID
    label: str
    metadata: dict = field(default_factory=dict)


@dataclass
class TurnNode:
    id: UUID
    speaker_id: UUID
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    acoustic_labels: dict[str, str] = field(default_factory=dict)
    embedding_id: Optional[UUID] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EmbeddingNode:
    id: UUID
    turn_id: UUID
    vector: list[float]
    dims: int
    head: str  # "emotion" | "prosody" | "asr" | "speaker"
    metadata: dict = field(default_factory=dict)


@dataclass
class EventNode:
    id: UUID
    event_type: str  # "laughter" | "overlap" | "long_pause" | "filler" | "cough" | "silence"
    start_ms: int
    end_ms: int
    speaker_id: Optional[UUID] = None
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: UUID
    target_id: UUID
    relation: Literal[
        "spoken_by", "followed_by", "responds_to", "interrupts",
        "has_embedding", "has_event", "overlaps_with", "semantically_similar"
    ]
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ConversationGraph:
    session_id: UUID
    speakers: list[SpeakerNode]
    turns: list[TurnNode]
    embeddings: list[EmbeddingNode]
    events: list[EventNode]
    edges: list[GraphEdge]
    metadata: dict = field(default_factory=dict)

    @property
    def start_ms(self) -> int:
        return min((t.start_ms for t in self.turns), default=0)

    @property
    def end_ms(self) -> int:
        return max((t.end_ms for t in self.turns), default=0)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def speaker_count(self) -> int:
        return len(self.speakers)

    @property
    def turn_count(self) -> int:
        return len(self.turns)
