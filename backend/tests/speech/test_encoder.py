import pytest
import torch

from app.speech.encoder import SpeechEncoder
from app.speech.types import AcousticEmbedding


class _DummyModel(torch.nn.Module):
    _encoder_version = "dummy@1.0"

    def __init__(self):
        super().__init__()
        self._t = torch.nn.Parameter(torch.randn(1, 256))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self._t.expand(x.size(0), -1)


@pytest.fixture
def encoder() -> SpeechEncoder:
    enc = SpeechEncoder(device="cpu")
    enc._model = _DummyModel()
    enc._model.eval()
    return enc


@pytest.mark.asyncio
async def test_load_model(monkeypatch):
    async def _mock_load(*args, **kwargs):
        return _DummyModel()
    monkeypatch.setattr("app.speech.encoder._async_torch_load", _mock_load)
    enc = SpeechEncoder(device="cpu")
    assert not enc.is_loaded
    await enc.load_model("dummy-checkpoint")
    assert enc.is_loaded


@pytest.mark.asyncio
async def test_load_model_idempotent(monkeypatch):
    async def _mock_load(*args, **kwargs):
        return _DummyModel()
    monkeypatch.setattr("app.speech.encoder._async_torch_load", _mock_load)
    enc = SpeechEncoder(device="cpu")
    await enc.load_model("ckpt")
    await enc.load_model("ckpt")
    assert enc.is_loaded


@pytest.mark.asyncio
async def test_encode_returns_acoustic_embedding(encoder):
    waveform = torch.randn(1, 16000)
    result = await encoder.encode(waveform)
    assert isinstance(result, AcousticEmbedding)
    assert result.dims == 256
    assert len(result.vector) == 256
    assert isinstance(result.encoder_version, str)


@pytest.mark.asyncio
async def test_encode_1d_waveform(encoder):
    waveform = torch.randn(16000)
    result = await encoder.encode(waveform)
    assert result.dims == 256


@pytest.mark.asyncio
async def test_encode_raises_on_not_loaded():
    enc = SpeechEncoder()
    with pytest.raises(RuntimeError, match="not loaded"):
        await enc.encode(torch.randn(1, 16000))


@pytest.mark.asyncio
async def test_encode_raises_on_3d_tensor(encoder):
    with pytest.raises(ValueError, match="3D"):
        await encoder.encode(torch.randn(2, 1, 16000))


@pytest.mark.asyncio
async def test_encode_raises_on_multichannel(encoder):
    with pytest.raises(ValueError, match="2 channels"):
        await encoder.encode(torch.randn(2, 16000))


@pytest.mark.asyncio
async def test_gpu_oom_fallback_to_cpu(monkeypatch):
    class _MockLoader:
        def __init__(self):
            self.call_count = 0
        async def __call__(self, checkpoint, device):
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError("CUDA out of memory")
            model = _DummyModel()
            return model

    monkeypatch.setattr("app.speech.encoder._async_torch_load", _MockLoader())
    enc = SpeechEncoder(device="cuda")
    assert enc.device == "cuda"
    await enc.load_model("fail-checkpoint")
    assert enc.device == "cpu"
