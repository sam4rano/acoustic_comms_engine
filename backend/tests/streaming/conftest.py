import struct
from unittest.mock import AsyncMock
from uuid import uuid4, UUID

import pytest
import pytest_asyncio

from app.streaming.manager import StreamSessionManager
from app.streaming.types import StreamSessionConfig, StreamMessage


@pytest_asyncio.fixture
def mock_manager() -> StreamSessionManager:
    """Real ``StreamSessionManager`` instance with default settings."""
    return StreamSessionManager(max_sessions=10, session_timeout_s=30.0)


@pytest_asyncio.fixture
def mock_dispatcher() -> AsyncMock:
    """Mock ``StreamDispatcher``."""
    dispatcher = AsyncMock()
    dispatcher.handle_frame.return_value = []
    dispatcher.handle_start.return_value = StreamMessage(
        type="state_change",
        payload={"status": "active"},
    )
    dispatcher.handle_end.return_value = StreamMessage(
        type="state_change",
        payload={"status": "closing"},
    )
    dispatcher.flush_pending.return_value = []
    return dispatcher


@pytest.fixture
def sample_stream_config() -> StreamSessionConfig:
    """Valid ``StreamSessionConfig`` fixture."""
    return StreamSessionConfig(
        user_id=uuid4(),
        session_id=uuid4(),
        sample_rate=16000,
        enabled_heads=["asr", "emotion"],
        language="en",
        vad_enabled=True,
        denoise_enabled=False,
    )


@pytest.fixture
def audio_frame_bytes() -> bytes:
    """Generate 320 bytes of simulated PCM16 audio (10 ms at 16 kHz)."""
    sample_count = 160
    samples = [int(32767 * 0.3 * _sine(i, 440, 16000)) for i in range(sample_count)]
    return struct.pack(f"<{sample_count}h", *samples)


@pytest.fixture
def valid_stream_message() -> dict:
    """Properly formatted dict for a start_session message."""
    return {
        "type": "start_session",
        "payload": {
            "user_id": str(uuid4()),
            "session_id": str(uuid4()),
            "sample_rate": 16000,
            "language": "en",
            "vad_enabled": True,
            "denoise_enabled": False,
        },
    }


def _sine(i: int, freq: float, sr: int) -> float:
    import math
    return math.sin(2 * math.pi * freq * i / sr)
