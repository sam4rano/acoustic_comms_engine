from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import torch

from app.audio.pipeline import AudioPipeline
from app.audio.types import AudioChunk as PipelineChunk, VADSegment
from app.speech.service import SpeechService
from app.speech.types import SpeechResult, TranscriptSegment
from app.streaming.dispatcher import StreamDispatcher, _bytes_to_tensor
from app.streaming.errors import InvalidFrameError
from app.streaming.manager import StreamSessionManager
from app.streaming.types import AudioFrame, StreamSessionConfig


class TestStreamDispatcher:
    """Tests for ``StreamDispatcher``."""

    @pytest.fixture
    def session_id(self) -> uuid4:
        return uuid4()

    @pytest.fixture
    def config(self, session_id: uuid4) -> StreamSessionConfig:
        return StreamSessionConfig(user_id=uuid4(), session_id=session_id)

    @pytest.fixture
    async def manager_with_session(
        self, config: StreamSessionConfig
    ) -> StreamSessionManager:
        m = StreamSessionManager()
        await m.create_session(config.session_id, config)
        await m.update_state(config.session_id, "active")
        return m

    @pytest.fixture
    def audio_pipeline(self) -> AudioPipeline:
        pipeline = MagicMock(spec=AudioPipeline)
        pipeline.process.return_value = [
            PipelineChunk(
                waveform=torch.randn(1, 160),
                sample_rate=16000,
                start_ms=0,
                end_ms=10,
                is_speech=True,
            )
        ]
        return pipeline

    @pytest.fixture
    def speech_service(self) -> SpeechService:
        service = AsyncMock(spec=SpeechService)
        result = SpeechResult(
            transcript=[
                TranscriptSegment(
                    text="hello world",
                    start_ms=0,
                    end_ms=10,
                    confidence=0.95,
                )
            ]
        )
        service.process_chunk = AsyncMock(return_value=result)
        return service  # type: ignore[return-value]

    @pytest.fixture
    def dispatcher(
        self,
        audio_pipeline: AudioPipeline,
        speech_service: SpeechService,
        manager_with_session: StreamSessionManager,
    ) -> StreamDispatcher:
        return StreamDispatcher(audio_pipeline, speech_service, manager_with_session)

    async def test_handle_frame_with_valid_audio(
        self, dispatcher: StreamDispatcher, session_id: uuid4, audio_frame_bytes: bytes
    ) -> None:
        frame = AudioFrame(data=audio_frame_bytes, sample_rate=16000, sequence=1)
        results = await dispatcher.handle_frame(session_id, frame)
        assert len(results) > 0
        assert any(m.type == "transcript" for m in results)

    async def test_handle_frame_with_silence(
        self,
        session_id: uuid4,
        config: StreamSessionConfig,
        audio_frame_bytes: bytes,
    ) -> None:
        pipeline = MagicMock(spec=AudioPipeline)
        pipeline.process.return_value = [
            PipelineChunk(
                waveform=torch.zeros(1, 160),
                sample_rate=16000,
                start_ms=0,
                end_ms=10,
                is_speech=False,
                vad_segments=[VADSegment(start_ms=0, end_ms=10, is_speech=False)],
            ),
        ]
        service = AsyncMock(spec=SpeechService)
        manager = StreamSessionManager()
        await manager.create_session(config.session_id, config)
        await manager.update_state(config.session_id, "active")

        dispatcher = StreamDispatcher(pipeline, service, manager)
        frame = AudioFrame(data=audio_frame_bytes, sample_rate=16000)
        results = await dispatcher.handle_frame(session_id, frame)
        assert len(results) == 0
        service.process_chunk.assert_not_called()

    async def test_handle_start_returns_ack(
        self, dispatcher: StreamDispatcher, session_id: uuid4, config: StreamSessionConfig
    ) -> None:
        msg = await dispatcher.handle_start(session_id, config)
        assert msg.type == "state_change"
        assert msg.payload["status"] == "active"
        assert msg.payload["session_id"] == str(session_id)

    async def test_handle_end_returns_summary(
        self, dispatcher: StreamDispatcher, session_id: uuid4
    ) -> None:
        msg = await dispatcher.handle_end(session_id)
        assert msg.type == "state_change"
        assert msg.payload["status"] == "closing"
        assert "frames_processed" in msg.payload

    async def test_error_on_bad_frame_returns_error_message(
        self, dispatcher: StreamDispatcher, session_id: uuid4
    ) -> None:
        frame = AudioFrame(data=b"not-valid-pcm", sample_rate=16000)
        with pytest.raises(InvalidFrameError):
            await dispatcher.handle_frame(session_id, frame)

    async def test_pipeline_error_does_not_crash(
        self,
        session_id: uuid4,
        config: StreamSessionConfig,
        audio_frame_bytes: bytes,
    ) -> None:
        pipeline = MagicMock(spec=AudioPipeline)
        pipeline.process.side_effect = RuntimeError("pipeline exploded")
        service = AsyncMock(spec=SpeechService)
        manager = StreamSessionManager()
        await manager.create_session(config.session_id, config)
        await manager.update_state(config.session_id, "active")

        dispatcher = StreamDispatcher(pipeline, service, manager)
        frame = AudioFrame(data=audio_frame_bytes, sample_rate=16000)
        results = await dispatcher.handle_frame(session_id, frame)
        assert len(results) == 1
        assert results[0].type == "error"

    async def test_dispatch_to_correct_session(
        self,
        dispatcher: StreamDispatcher,
        session_id: uuid4,
        config: StreamSessionConfig,
        manager_with_session: StreamSessionManager,
        audio_frame_bytes: bytes,
    ) -> None:
        frame = AudioFrame(data=audio_frame_bytes, sample_rate=16000)
        results = await dispatcher.handle_frame(session_id, frame)
        assert isinstance(results, list)
        state = await manager_with_session.get_session(session_id)
        assert state is not None
        assert state.frame_count > 0


class TestBytesToTensor:
    """Tests for the ``_bytes_to_tensor`` helper."""

    def test_converts_pcm16_bytes(self, audio_frame_bytes: bytes) -> None:
        tensor = _bytes_to_tensor(audio_frame_bytes, 16000)
        assert tensor.dim() == 2
        assert tensor.size(0) == 1
        assert tensor.dtype == torch.float32
        assert tensor.size(1) == 160

    def test_handles_empty_bytes(self) -> None:
        tensor = _bytes_to_tensor(b"", 16000)
        assert tensor.numel() == 0

    def test_values_in_range(self, audio_frame_bytes: bytes) -> None:
        tensor = _bytes_to_tensor(audio_frame_bytes, 16000)
        assert tensor.min() >= -1.0
        assert tensor.max() <= 1.0
