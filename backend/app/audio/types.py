from dataclasses import dataclass, field
from typing import Optional

import torch


@dataclass
class VADSegment:
    start_ms: int
    end_ms: int
    is_speech: bool


@dataclass
class AudioChunk:
    waveform: torch.Tensor
    sample_rate: int = 16000
    start_ms: int = 0
    end_ms: int = 0
    vad_segments: list[VADSegment] = field(default_factory=list)
    is_speech: bool = True
