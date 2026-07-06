import pytest
import torch


@pytest.fixture
def sample_waveform():
    """Synthetic 440 Hz sine wave at 16 kHz, 1 second."""
    sr = 16000
    t = torch.linspace(0, 1.0, sr, dtype=torch.float32)
    wav = 0.5 * torch.sin(2 * torch.pi * 440 * t).unsqueeze(0)
    return wav, sr


@pytest.fixture
def silent_waveform():
    """All-zeros tensor at 16 kHz, 1 second."""
    sr = 16000
    return torch.zeros(1, sr, dtype=torch.float32), sr


@pytest.fixture
def noisy_waveform():
    """440 Hz sine wave + Gaussian noise at 16 kHz, 1 second."""
    sr = 16000
    t = torch.linspace(0, 1.0, sr, dtype=torch.float32)
    wav = 0.5 * torch.sin(2 * torch.pi * 440 * t)
    noise = 0.1 * torch.randn(sr, dtype=torch.float32)
    wav = (wav + noise).unsqueeze(0)
    return wav, sr


@pytest.fixture
def short_waveform():
    """Very short waveform (32 samples) for edge cases."""
    sr = 16000
    return torch.randn(1, 32, dtype=torch.float32), sr
