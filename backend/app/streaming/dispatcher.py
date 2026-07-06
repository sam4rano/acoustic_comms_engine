import logging
from typing import Optional
from uuid import UUID

import torch

from app.audio.pipeline import AudioPipeline, PipelineConfig
from app.audio.types import AudioChunk as AudioPipelineChunk
from app.speech.service import AudioChunk as SpeechAudioChunk, SpeechService
from app.speech.types import SpeechResult
from app.streaming.errors import InvalidFrameError
from app.streaming.manager import StreamSessionManager
from app.streaming.types import AudioFrame, StreamMessage, StreamSessionConfig

logger = logging.getLogger(__name__)

_RESULT_BATCH_SIZE = 5


def _speech_result_to_messages(result: SpeechResult) -> list[StreamMessage]:
    """Convert a ``SpeechResult`` into one or more ``StreamMessage`` objects."""
    messages: list[StreamMessage] = []

    for seg in result.transcript:
        messages.append(
            StreamMessage(
                type="transcript",
                payload={
                    "text": seg.text,
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "confidence": seg.confidence,
                    "is_partial": seg.is_partial,
                    "speaker_label": seg.speaker_label,
                    "turn_id": str(result.turn_id),
                },
            )
        )

    for label in result.acoustic_labels:
        messages.append(
            StreamMessage(
                type="acoustic_label",
                payload={
                    "head": label.head,
                    "label": label.label,
                    "confidence": label.confidence,
                    "metadata": label.metadata,
                    "turn_id": str(result.turn_id),
                },
            )
        )

    for event in result.events:
        messages.append(
            StreamMessage(
                type="audio_event",
                payload={
                    "event_type": event.event_type,
                    "start_ms": event.start_ms,
                    "end_ms": event.end_ms,
                    "confidence": event.confidence,
                    "turn_id": str(result.turn_id),
                },
            )
        )

    return messages


def _is_speech_chunk(chunk: AudioPipelineChunk) -> bool:
    return chunk.is_speech or any(s.is_speech for s in chunk.vad_segments)


class StreamDispatcher:
    """Coordinates audio frame processing through the pipeline.

    Receives raw audio frames from WebSocket, passes them through
    ``AudioPipeline``, feeds speech segments to ``SpeechService``,
    and returns structured results as ``StreamMessage`` objects.
    """

    def __init__(
        self,
        audio_pipeline: AudioPipeline,
        speech_service: SpeechService,
        manager: StreamSessionManager,
    ) -> None:
        self._audio_pipeline = audio_pipeline
        self._speech_service = speech_service
        self._manager = manager
        self._pending_messages: dict[UUID, list[StreamMessage]] = {}

    async def handle_frame(
        self,
        session_id: UUID,
        frame: AudioFrame,
    ) -> list[StreamMessage]:
        """Process a single audio frame.

        Returns a (possibly empty) list of result messages.
        """
        try:
            waveform = _bytes_to_tensor(frame.data, frame.sample_rate)
        except Exception as exc:
            await self._manager.increment_errors(session_id)
            raise InvalidFrameError(f"Failed to decode frame: {exc}") from exc

        try:
            chunks = self._audio_pipeline.process(waveform, frame.sample_rate)
        except Exception as exc:
            await self._manager.increment_errors(session_id)
            return [
                StreamMessage(
                    type="error",
                    payload={"message": f"Pipeline error: {exc}", "sequence": frame.sequence},
                )
            ]

        await self._manager.increment_frames(session_id)

        session = await self._manager.get_session(session_id)
        if session is None:
            return []

        results: list[StreamMessage] = []

        for chunk in chunks:
            if not _is_speech_chunk(chunk):
                continue

            speech_chunk = SpeechAudioChunk(
                waveform=chunk.waveform,
                sample_rate=chunk.sample_rate,
                chunk_id=str(session_id),
            )

            try:
                speech_result = await self._speech_service.process_chunk(
                    speech_chunk,
                    session.config.enabled_heads,
                )
            except Exception as exc:
                logger.exception("Speech service error for session %s", session_id)
                await self._manager.increment_errors(session_id)
                results.append(
                    StreamMessage(
                        type="error",
                        payload={
                            "message": f"Speech processing error: {exc}",
                            "sequence": frame.sequence,
                        },
                    )
                )
                continue

            messages = _speech_result_to_messages(speech_result)
            results.extend(messages)

        return results

    async def handle_start(
        self,
        session_id: UUID,
        config: StreamSessionConfig,
    ) -> StreamMessage:
        """Return an acknowledgment for a newly-created session."""
        await self._manager.update_state(session_id, "active")
        return StreamMessage(
            type="state_change",
            payload={
                "session_id": str(session_id),
                "status": "active",
                "config": {
                    "sample_rate": config.sample_rate,
                    "enabled_heads": config.enabled_heads,
                    "language": config.language,
                    "vad_enabled": config.vad_enabled,
                    "denoise_enabled": config.denoise_enabled,
                },
            },
        )

    async def handle_end(self, session_id: UUID) -> StreamMessage:
        """Return a summary for a session that is ending."""
        session = await self._manager.get_session(session_id)
        if session is not None:
            await self._manager.update_state(session_id, "closing")

        frame_count = session.frame_count if session else 0
        error_count = session.error_count if session else 0

        return StreamMessage(
            type="state_change",
            payload={
                "session_id": str(session_id),
                "status": "closing",
                "frames_processed": frame_count,
                "errors": error_count,
            },
        )

    def _maybe_batch_results(
        self,
        session_id: UUID,
        results: list[StreamMessage],
    ) -> list[StreamMessage]:
        """Accumulate small result messages and emit them as batches."""
        if not results:
            return []

        pending = self._pending_messages.setdefault(session_id, [])
        pending.extend(results)

        if len(pending) >= _RESULT_BATCH_SIZE:
            batch = pending[:]
            self._pending_messages[session_id] = []
            return [
                StreamMessage(
                    type="transcript",
                    payload={"batched": [m.payload for m in batch]},
                )
            ]

        return []

    async def flush_pending(self, session_id: UUID) -> list[StreamMessage]:
        """Emit any remaining batched results for ``session_id``."""
        pending = self._pending_messages.pop(session_id, [])
        if pending:
            return [
                StreamMessage(
                    type="transcript",
                    payload={"batched": [m.payload for m in pending]},
                )
            ]
        return []


def _bytes_to_tensor(data: bytes, sample_rate: int) -> torch.Tensor:
    """Convert raw PCM16 mono bytes to a ``[1, T]`` float32 tensor."""
    import struct

    count = len(data) // 2
    fmt = f"<{count}h"
    samples = struct.unpack(fmt, data)
    tensor = torch.tensor(samples, dtype=torch.float32) / 32768.0
    return tensor.unsqueeze(0)
