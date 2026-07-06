import math
import logging

import torch

from app.audio.types import AudioChunk, VADSegment

logger = logging.getLogger(__name__)


class Chunker:
    """Splits audio into fixed-size frames with optional overlap.

    Each chunk carries ``start_ms`` / ``end_ms`` timestamps and
    a copy of the VAD segments that overlap with its time window.
    """

    @staticmethod
    def chunk(
        waveform: torch.Tensor,
        chunk_size_ms: int = 30,
        overlap_ms: int = 10,
        sample_rate: int = 16000,
        vad_segments: list[VADSegment] | None = None,
    ) -> list[AudioChunk]:
        """Split ``waveform`` into overlapping chunks.

        Args:
            waveform: ``[1, T]`` float32 mono tensor.
            chunk_size_ms: Duration of each chunk in ms (default 30).
            overlap_ms: Overlap between consecutive chunks in ms (default 10).
            sample_rate: Sample rate in Hz (default 16 000).
            vad_segments: Optional list of ``VADSegment`` to attach to chunks.

        Returns:
            List of ``AudioChunk`` objects.
        """
        if waveform.numel() == 0:
            return []

        if waveform.dim() != 2 or waveform.size(0) != 1:
            raise ValueError(
                f"Expected shape [1, T], got {list(waveform.shape)}"
            )

        total_samples = waveform.size(-1)
        total_duration_ms = int(total_samples / sample_rate * 1000)
        chunk_size = int(sample_rate * chunk_size_ms / 1000)
        hop = int(sample_rate * (chunk_size_ms - overlap_ms) / 1000)

        if chunk_size_ms <= overlap_ms:
            raise ValueError(
                f"overlap_ms ({overlap_ms}) must be less than chunk_size_ms ({chunk_size_ms})"
            )

        if chunk_size < 1:
            raise ValueError(
                f"chunk_size_ms={chunk_size_ms} yields zero samples "
                f"at sample_rate={sample_rate}"
            )

        chunks: list[AudioChunk] = []
        start_sample = 0

        while start_sample < total_samples:
            end_sample = min(start_sample + chunk_size, total_samples)
            actual_size = end_sample - start_sample

            fragment = waveform[:, start_sample:end_sample]

            # Pad trailing partial chunk with zeros
            if actual_size < chunk_size:
                pad = torch.zeros(1, chunk_size - actual_size, dtype=torch.float32)
                fragment = torch.cat([fragment, pad], dim=1)
                end_sample = start_sample + chunk_size

            start_ms = int(start_sample / sample_rate * 1000)
            end_ms = int(end_sample / sample_rate * 1000)

            # Filter VAD segments that overlap with this chunk
            chunk_vad: list[VADSegment] = []
            is_speech = True
            if vad_segments:
                for seg in vad_segments:
                    if seg.start_ms < end_ms and seg.end_ms > start_ms:
                        chunk_vad.append(seg)
                # A chunk is considered speech if any VAD segment in it is speech
                is_speech = any(s.is_speech for s in chunk_vad)

            chunks.append(
                AudioChunk(
                    waveform=fragment,
                    sample_rate=sample_rate,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    vad_segments=chunk_vad,
                    is_speech=is_speech,
                )
            )

            start_sample += hop

        return chunks
