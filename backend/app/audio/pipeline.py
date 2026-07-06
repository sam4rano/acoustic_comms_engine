import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch
import torchaudio

from app.audio.chunking import Chunker
from app.audio.denoise import Denoiser
from app.audio.errors import AudioProcessingError
from app.audio.resample import Resampler
from app.audio.types import AudioChunk, VADSegment
from app.audio.vad import VAD

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    resample: bool = True
    vad: bool = True
    denoise: bool = True
    chunk: bool = True
    target_sample_rate: int = 16000
    chunk_size_ms: int = 30
    chunk_overlap_ms: int = 10


class AudioPipeline:
    """End-to-end audio processing pipeline.

    Chains: resample → VAD → denoise → chunk.

    Each stage can be independently disabled via ``PipelineConfig``.
    When VAD is skipped the pipeline treats the entire waveform as speech.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    def process(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
    ) -> list[AudioChunk]:
        """Run the full pipeline on ``waveform``.

        Args:
            waveform: ``[1, T]`` float32 mono tensor.
            sample_rate: Sample rate of ``waveform`` in Hz.

        Returns:
            List of ``AudioChunk`` objects.

        Raises:
            AudioProcessingError: If a required processing step fails.
        """
        if waveform.numel() == 0:
            return []

        data = waveform
        orig_sr = sample_rate

        # 1. Resample
        if self.config.resample and orig_sr != self.config.target_sample_rate:
            try:
                data = Resampler.resample(data, orig_sr, self.config.target_sample_rate)
            except Exception as exc:
                raise AudioProcessingError(f"Resampling failed: {exc}") from exc

        effective_sr = self.config.target_sample_rate if self.config.resample else orig_sr

        # 2. VAD
        vad_segments: list[VADSegment] = []
        if self.config.vad:
            try:
                vad_segments = VAD.detect_activity(data, sample_rate=effective_sr)
            except Exception as exc:
                raise AudioProcessingError(f"VAD failed: {exc}") from exc

        # 3. Denoise
        if self.config.denoise:
            try:
                data = Denoiser.denoise(data, sample_rate=effective_sr)
            except Exception as exc:
                raise AudioProcessingError(f"Denoising failed: {exc}") from exc

        # 4. Chunk
        if self.config.chunk:
            try:
                chunks = Chunker.chunk(
                    data,
                    chunk_size_ms=self.config.chunk_size_ms,
                    overlap_ms=self.config.chunk_overlap_ms,
                    sample_rate=effective_sr,
                    vad_segments=vad_segments or None,
                )
            except Exception as exc:
                raise AudioProcessingError(f"Chunking failed: {exc}") from exc
        else:
            chunks = [
                AudioChunk(
                    waveform=data,
                    sample_rate=effective_sr,
                    start_ms=0,
                    end_ms=int(data.size(-1) / effective_sr * 1000),
                    vad_segments=vad_segments,
                )
            ]

        return chunks

    def process_file(self, path: str | Path) -> list[AudioChunk]:
        """Load audio from ``path`` and run the pipeline.

        Args:
            path: Path to an audio file (any format torchaudio supports).

        Returns:
            List of ``AudioChunk`` objects.
        """
        path = Path(path)
        if not path.exists():
            raise AudioProcessingError(f"Audio file not found: {path}")

        try:
            waveform, sample_rate = torchaudio.load(str(path), normalize=True)
        except Exception as exc:
            raise AudioProcessingError(
                f"Failed to load audio file {path}: {exc}"
            ) from exc

        # Convert to mono
        if waveform.size(0) > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        return self.process(waveform, sample_rate)
