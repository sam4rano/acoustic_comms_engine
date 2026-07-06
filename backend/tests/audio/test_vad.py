"""Tests for VAD module.

Silero VAD is mocked at the module level to avoid requiring
a model download or GPU in CI.
"""

from unittest.mock import ANY, patch

import pytest
import torch

from app.audio.errors import VADError
from app.audio.types import VADSegment
from app.audio.vad import VAD


def _make_speech_timestamps(samples_list: list[tuple[int, int]]) -> list[dict]:
    """Helper to create the list-of-dicts returned by get_speech_timestamps."""
    return [{"start": s, "end": e} for s, e in samples_list]


class TestVAD:
    def test_detect_speech_in_sine_wave(self, sample_waveform):
        """Silero VAD should detect speech activity in a sine wave."""
        wav, sr = sample_waveform

        with patch.object(VAD, "_model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=_make_speech_timestamps([(100, 8000)]),
            ):
                segments = VAD.detect_activity(wav, sr)

        assert len(segments) >= 1
        assert any(s.is_speech for s in segments)

    def test_all_silence_returns_silence_segment(self, silent_waveform):
        """All-zeros input should produce a single silence VADSegment."""
        wav, sr = silent_waveform

        with patch.object(VAD, "_model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[],
            ):
                segments = VAD.detect_activity(wav, sr)

        assert len(segments) == 1
        assert segments[0].is_speech is False
        assert segments[0].start_ms == 0
        assert segments[0].end_ms > 0

    def test_segments_have_correct_ms_boundaries(self, sample_waveform):
        """VADSegment start_ms and end_ms should be accurate given sample positions."""
        wav, sr = sample_waveform
        # 1 second at 16 kHz = 16000 samples
        # Speech from sample 0 → 7999 → 0 ms → ~500 ms
        # Silence from sample 8000 → 15999 → ~500 ms → 1000 ms
        speech_samples = [(0, 8000)]

        with patch.object(VAD, "_model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=_make_speech_timestamps(speech_samples),
            ):
                segments = VAD.detect_activity(wav, sr)

        assert len(segments) == 2
        # First segment should be speech (0–500 ms)
        assert segments[0].is_speech is True
        assert segments[0].start_ms == 0
        assert segments[0].end_ms == 500
        # Second segment should be silence (500–1000 ms)
        assert segments[1].is_speech is False
        assert segments[1].start_ms == 500
        assert segments[1].end_ms == 1000

    def test_all_speech_returns_single_speech_segment(self, sample_waveform):
        """Entire waveform detected as speech → one segment."""
        wav, sr = sample_waveform

        with patch.object(VAD, "_model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=_make_speech_timestamps([(0, 16000)]),
            ):
                segments = VAD.detect_activity(wav, sr)

        assert len(segments) == 1
        assert segments[0].is_speech is True
        assert segments[0].start_ms == 0
        assert segments[0].end_ms == 1000

    def test_empty_input_returns_empty_list(self):
        """Empty waveform should return an empty list without calling the model."""
        wav = torch.empty(1, 0)

        with patch.object(VAD, "_model", None):
            segments = VAD.detect_activity(wav, 16000)

        assert segments == []

    def test_wrong_shape_raises_error(self):
        """Non-[1, T] input should raise VADError."""
        wav = torch.randn(2, 16000)

        with patch.object(VAD, "_model", None):
            with pytest.raises(VADError, match="Expected shape"):
                VAD.detect_activity(wav, 16000)

    def test_load_model_returns_cached_model(self):
        """load_model() should return the cached model object."""
        mock_model = object()
        with patch.object(VAD, "_model", mock_model):
            model = VAD.load_model()
            assert model is mock_model

    def test_model_load_error_raises_vad_error(self):
        """If model loading fails, VADError should be raised."""
        with patch.object(VAD, "_model", None):
            with patch("torch.hub.load", side_effect=Exception("download failed")):
                with pytest.raises(VADError, match="Failed to load"):
                    VAD.load_model()
