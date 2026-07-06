import pytest
import torch

from app.audio.errors import ResamplingError
from app.audio.resample import Resampler


class TestResampler:
    def test_resample_48k_to_16k_preserves_duration(self):
        """Resampling 48 kHz → 16 kHz should produce 3× fewer samples."""
        sr = 48000
        duration_s = 1.0
        wav = torch.randn(1, int(sr * duration_s))
        result = Resampler.resample(wav, sr, 16000)
        # 48000 samples → 16000 samples (approximately)
        expected = 16000
        # Allow small rounding difference
        assert abs(result.size(-1) - expected) <= 2
        assert result.dtype == torch.float32

    def test_resample_preserves_dtype(self):
        """Output dtype must be float32 regardless of input."""
        sr = 44100
        wav = torch.randn(1, 44100, dtype=torch.float32)
        result = Resampler.resample(wav, sr, 16000)
        assert result.dtype == torch.float32

    def test_resample_same_rate_returns_copy(self):
        """When orig_sr == target_sr the input should be returned as-is."""
        sr = 16000
        wav = torch.randn(1, 16000)
        result = Resampler.resample(wav, sr, 16000)
        assert result is wav  # Same object, no copy

    def test_empty_input_raises_error(self):
        """Empty tensor should raise ResamplingError."""
        wav = torch.empty(1, 0)
        with pytest.raises(ResamplingError, match="Cannot resample empty waveform"):
            Resampler.resample(wav, 16000, 8000)

    def test_wrong_shape_raises_error(self):
        """Tensor with wrong number of channels should raise."""
        wav = torch.randn(2, 16000)  # stereo
        with pytest.raises(ResamplingError, match="Expected shape"):
            Resampler.resample(wav, 16000, 8000)

    def test_resample_non_standard_rates(self):
        """44.1 kHz → 16 kHz should work without error."""
        sr = 44100
        wav = torch.randn(1, 44100)
        result = Resampler.resample(wav, sr, 16000)
        assert result.size(-1) > 0
        assert result.dtype == torch.float32

    def test_resample_8k_to_16k(self):
        """8 kHz → 16 kHz (upsampling)."""
        sr = 8000
        wav = torch.randn(1, 8000)
        result = Resampler.resample(wav, sr, 16000)
        expected = 16000
        assert abs(result.size(-1) - expected) <= 2

    def test_resampler_uses_cached_instance(self):
        """Calling resample twice with same (orig, target) should reuse cache."""
        sr = 48000
        wav = torch.randn(1, 48000)
        r1 = Resampler.resample(wav, sr, 16000)
        # Access internal cache key
        key = (48000, 16000)
        assert key in Resampler._instances
        # Clear the reference count check
        r2 = Resampler.resample(wav, sr, 16000)
        assert r1.size(-1) == r2.size(-1)
