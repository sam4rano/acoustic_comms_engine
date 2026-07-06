import random
from collections.abc import AsyncGenerator

import pytest_asyncio
import torch

from app.speech.encoder import SpeechEncoder
from app.speech.registry import HeadRegistry
from app.speech.service import AudioChunk, SpeechService
from app.speech.types import AcousticEmbedding


@pytest_asyncio.fixture
def mock_embedding() -> AcousticEmbedding:
    dims = 256
    vector = [random.uniform(-1.0, 1.0) for _ in range(dims)]
    return AcousticEmbedding(
        vector=vector,
        dims=dims,
        encoder_version="test-encoder@1.0",
    )


@pytest_asyncio.fixture
def mock_chunk() -> AudioChunk:
    return AudioChunk(
        waveform=torch.randn(1, 16000),
        sample_rate=16000,
        chunk_id="test-chunk-001",
    )


@pytest_asyncio.fixture
def head_registry() -> HeadRegistry:
    return HeadRegistry()


@pytest_asyncio.fixture
async def speech_service() -> AsyncGenerator[SpeechService, None]:
    encoder = SpeechEncoder(device="cpu")

    class _MockModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self._encoder_version = "test-encoder@1.0"

        def forward(self, waveform: torch.Tensor) -> torch.Tensor:
            return torch.randn(1, 256)

    encoder._model = _MockModel()
    encoder._model.eval()

    registry = HeadRegistry()
    service = SpeechService(encoder=encoder, registry=registry)
    yield service
