from enum import StrEnum


class SessionStatus(StrEnum):
    CREATED = "created"
    LIVE = "live"
    PROCESSING = "processing"
    READY = "ready"
    ARCHIVED = "archived"
    ABORTED = "aborted"


class AudioEventType(StrEnum):
    SILENCE = "silence"
    NOISE = "noise"
    OVERLAP = "overlap"
    LOUDNESS = "loudness"
    SPEECH = "speech"
    OTHER = "other"
