from dataclasses import dataclass, field
from uuid import UUID, uuid4
from typing import Optional


@dataclass
class TranscriptSegment:
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    is_partial: bool = False
    speaker_label: Optional[str] = None


@dataclass
class AcousticEmbedding:
    vector: list[float]
    dims: int
    encoder_version: str


@dataclass
class AcousticLabel:
    head: str
    label: str
    confidence: float
    metadata: dict = field(default_factory=dict)


@dataclass
class AudioEvent:
    event_type: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0


@dataclass
class SpeechResult:
    turn_id: UUID = field(default_factory=uuid4)
    transcript: list[TranscriptSegment] = field(default_factory=list)
    speaker_label: Optional[str] = None
    acoustic_labels: list[AcousticLabel] = field(default_factory=list)
    embedding: Optional[AcousticEmbedding] = None
    events: list[AudioEvent] = field(default_factory=list)
