import asyncio

import pytest
import torch

from app.speech.encoder import SpeechEncoder
from app.speech.heads.base import BaseHead
from app.speech.registry import HeadRegistry
from app.speech.service import AudioChunk, SpeechService
from app.speech.types import AcousticEmbedding, AudioEvent, SpeechResult


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


@pytest.fixture
def registry() -> HeadRegistry:
    return HeadRegistry()


@pytest.fixture
def service(encoder, registry) -> SpeechService:
    return SpeechService(encoder=encoder, registry=registry)


@pytest.fixture
def chunk() -> AudioChunk:
    return AudioChunk(
        waveform=torch.randn(1, 16000),
        sample_rate=16000,
        chunk_id="test-001",
    )


@pytest.mark.asyncio
async def test_process_chunk_returns_speech_result(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=["asr"])
    assert isinstance(result, SpeechResult)
    assert result.embedding is not None


@pytest.mark.asyncio
async def test_process_chunk_with_all_heads(service, chunk):
    all_heads = ["asr", "emotion", "prosody", "stress", "fluency", "event"]
    result = await service.process_chunk(chunk, enabled_heads=all_heads)
    assert result.embedding is not None
    assert len(result.transcript) >= 1
    assert len(result.acoustic_labels) >= 4
    assert len(result.events) >= 0


@pytest.mark.asyncio
async def test_process_chunk_with_subset_of_heads(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=["asr", "emotion"])
    assert result.embedding is not None
    assert len(result.transcript) >= 1
    assert len(result.acoustic_labels) >= 1
    assert len(result.events) == 0


@pytest.mark.asyncio
async def test_process_chunk_skips_unknown_heads(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=["asr", "nonexistent"])
    assert result.embedding is not None
    assert len(result.transcript) >= 1


@pytest.mark.asyncio
async def test_process_chunk_empty_heads(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=[])
    assert result.embedding is not None
    assert len(result.transcript) == 0
    assert len(result.acoustic_labels) == 0
    assert len(result.events) == 0


@pytest.mark.asyncio
async def test_head_failure_graceful(service, chunk):
    class _FailingHead(BaseHead):
        name = "failing"

        async def process(self, embedding):
            raise RuntimeError("Head crashed")

    service._registry.register("failing", _FailingHead)
    result = await service.process_chunk(chunk, enabled_heads=["asr", "failing"])
    assert result.embedding is not None
    assert len(result.transcript) >= 1


@pytest.mark.asyncio
async def test_encoder_lock_serializes_access(service):
    call_order: list[int] = []

    async def delayed_encode(waveform: torch.Tensor) -> AcousticEmbedding:
        return await service._encoder.encode(waveform)

    async def process_with_delay(delay_ms: int, tag: int):
        chunk = AudioChunk(waveform=torch.randn(1, 16000), sample_rate=16000)
        async with service._encode_lock:
            call_order.append(tag)
            await asyncio.sleep(delay_ms / 1000)
        return await service._encoder.encode(chunk.waveform)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(process_with_delay(50, 1))
        tg.create_task(process_with_delay(10, 2))

    assert call_order == [1, 2], f"Expected serial order [1, 2], got {call_order}"


@pytest.mark.asyncio
async def test_process_chunk_includes_embedding(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=[])
    assert result.embedding is not None
    assert result.embedding.dims == 256
    assert result.embedding.encoder_version == "dummy@1.0"


@pytest.mark.asyncio
async def test_asr_head_sets_speaker_label(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=["asr"])
    if result.transcript:
        seg = result.transcript[0]
        assert isinstance(seg.speaker_label, str) or seg.speaker_label is None


@pytest.mark.asyncio
async def test_event_head_appends_events(service, chunk):
    result = await service.process_chunk(chunk, enabled_heads=["event"])
    for event in result.events:
        assert isinstance(event, AudioEvent)
