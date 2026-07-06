from dataclasses import dataclass, field
from uuid import UUID
from typing import Literal, Optional
from datetime import datetime, timezone


@dataclass
class AudioFrame:
    data: bytes
    sample_rate: int = 16000
    sequence: int = 0
    timestamp_ms: int = 0


@dataclass
class StreamMessage:
    type: Literal[
        "audio_frame", "start_session", "end_session",
        "transcript", "acoustic_label", "audio_event",
        "error", "state_change", "ping", "pong", "config_update"
    ]
    payload: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_id: Optional[str] = None


@dataclass
class StreamSessionConfig:
    user_id: UUID
    session_id: UUID
    sample_rate: int = 16000
    enabled_heads: list[str] = field(default_factory=lambda: [
        "asr", "emotion", "prosody", "stress", "fluency", "event"
    ])
    language: str = "en"
    vad_enabled: bool = True
    denoise_enabled: bool = False


@dataclass
class StreamSessionState:
    config: StreamSessionConfig
    status: Literal["connecting", "active", "paused", "closing", "closed"]
    connected_at: datetime
    frame_count: int = 0
    last_frame_at: Optional[datetime] = None
    error_count: int = 0
