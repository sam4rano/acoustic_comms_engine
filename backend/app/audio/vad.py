import logging
from typing import Optional

import torch

from app.audio.errors import VADError
from app.audio.types import VADSegment

logger = logging.getLogger(__name__)


class VAD:
    """Voice Activity Detection wrapping Silero VAD.

    The underlying model is loaded lazily on first call so that
    importing the module does not trigger a model download.
    """

    _model: Optional[object] = None

    # ── internal helpers ────────────────────────────────────────────────

    @classmethod
    def _load_silero_vad(cls) -> object:
        """Download and cache the Silero VAD model (lazy)."""
        if cls._model is not None:
            return cls._model

        try:
            import silero_vad

            cls._model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
        except Exception as exc:
            raise VADError(f"Failed to load Silero VAD model: {exc}") from exc

        return cls._model

    @classmethod
    def _get_speech_timestamps(
        cls, waveform: torch.Tensor, model: object, sampling_rate: int
    ) -> list[dict]:
        """Wrap ``silero_vad.get_speech_timestamps`` for mockability."""
        import silero_vad

        return silero_vad.get_speech_timestamps(
            waveform, model, sampling_rate=sampling_rate
        )

    # ── public API ──────────────────────────────────────────────────────

    @classmethod
    def load_model(cls) -> object:
        """Explicitly load (or return already-loaded) Silero VAD model."""
        return cls._load_silero_vad()

    @classmethod
    def detect_activity(
        cls,
        waveform: torch.Tensor,
        sample_rate: int = 16000,
    ) -> list[VADSegment]:
        """Run voice activity detection on ``waveform``.

        Args:
            waveform: ``[1, T]`` float32 mono tensor.
            sample_rate: Sample rate of ``waveform`` (default 16 000).

        Returns:
            List of ``VADSegment`` with millisecond boundaries.

        Raises:
            VADError: If the model could not be loaded or inference fails.
        """
        if waveform.numel() == 0:
            return []

        if waveform.dim() != 2 or waveform.size(0) != 1:
            raise VADError(
                f"Expected shape [1, T], got {list(waveform.shape)}"
            )

        # Silero VAD requires at least 512 samples at 16 kHz
        min_samples = max(512, int(sample_rate / 31.25))
        if waveform.size(-1) < min_samples:
            if waveform.size(-1) < 64:
                # Too short to be useful — return single non-speech segment
                return [VADSegment(start_ms=0, end_ms=1, is_speech=False)]
            # Pad with zeros
            pad = torch.zeros(1, min_samples - waveform.size(-1))
            waveform = torch.cat([waveform, pad], dim=-1)
            logger.debug("Padded short waveform (%d → %d samples)", waveform.size(-1) - pad.size(-1) + pad.size(-1), waveform.size(-1))

        model = cls._load_silero_vad()

        try:
            speech_timestamps = cls._get_speech_timestamps(
                waveform, model, sampling_rate=sample_rate
            )
        except Exception as exc:
            raise VADError(f"VAD inference failed: {exc}") from exc

        segments: list[VADSegment] = []
        total_samples = waveform.size(-1)
        total_duration_ms = int(total_samples / sample_rate * 1000)

        if not speech_timestamps:
            segments.append(VADSegment(start_ms=0, end_ms=total_duration_ms, is_speech=False))
            return segments

        # Build speech segments sorted by start sample
        speech_starts: list[int] = []
        speech_ends: list[int] = []
        for ts in speech_timestamps:
            start_s = int(ts["start"])
            end_s = int(ts["end"])
            speech_starts.append(start_s)
            speech_ends.append(end_s)

        prev_end_s = 0

        for i in range(len(speech_starts)):
            # Gap before this speech segment → silence
            if speech_starts[i] > prev_end_s:
                silence_start_ms = int(prev_end_s / sample_rate * 1000)
                silence_end_ms = int(speech_starts[i] / sample_rate * 1000)
                if silence_end_ms > silence_start_ms:
                    segments.append(
                        VADSegment(
                            start_ms=silence_start_ms,
                            end_ms=silence_end_ms,
                            is_speech=False,
                        )
                    )

            # Speech segment
            speech_start_ms = int(speech_starts[i] / sample_rate * 1000)
            speech_end_ms = int(speech_ends[i] / sample_rate * 1000)
            if speech_end_ms > speech_start_ms:
                segments.append(
                    VADSegment(
                        start_ms=speech_start_ms,
                        end_ms=speech_end_ms,
                        is_speech=True,
                    )
                )
            prev_end_s = speech_ends[i]

        # Trailing silence
        if prev_end_s < total_samples:
            tail_start_ms = int(prev_end_s / sample_rate * 1000)
            if total_duration_ms > tail_start_ms:
                segments.append(
                    VADSegment(
                        start_ms=tail_start_ms,
                        end_ms=total_duration_ms,
                        is_speech=False,
                    )
                )

        return segments
