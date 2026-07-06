import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import torch

from .encoder import SpeechEncoder
from .registry import HeadRegistry
from .types import SpeechResult

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """Input audio chunk for processing."""
    waveform: torch.Tensor
    sample_rate: int = 16000
    chunk_id: Optional[str] = None


class SpeechService:
    def __init__(self, encoder: SpeechEncoder, registry: HeadRegistry):
        self._encoder = encoder
        self._registry = registry
        self._encode_lock = asyncio.Lock()

    async def process_chunk(
        self,
        chunk: AudioChunk,
        enabled_heads: list[str],
    ) -> SpeechResult:
        result = SpeechResult()

        # 1. Encode
        async with self._encode_lock:
            embedding = await self._encoder.encode(chunk.waveform)

        result.embedding = embedding

        # 2. Run enabled heads concurrently
        coros: list[tuple[str, asyncio.Task]] = []
        for head_name in enabled_heads:
            try:
                head = self._registry.get_head(head_name)
            except KeyError:
                logger.warning("Unknown head skipped: %s", head_name)
                continue
            coros.append((head_name, asyncio.ensure_future(self._safe_process(head, head_name, embedding))))

        if coros:
            done, _ = await asyncio.wait(
                [t for _, t in coros], return_when=asyncio.ALL_COMPLETED
            )
            name_map = {id(t): n for n, t in coros}

            for fut in done:
                head_name = name_map.get(id(fut), "?")
                try:
                    outputs = fut.result()
                except Exception:
                    logger.exception("Head %s raised an unhandled exception", head_name)
                    continue

                if head_name == "asr":
                    for item in outputs:
                        from .types import TranscriptSegment
                        if isinstance(item, TranscriptSegment):
                            result.transcript.append(item)
                            if item.speaker_label:
                                result.speaker_label = item.speaker_label
                elif head_name == "event":
                    for item in outputs:
                        from .types import AudioEvent
                        if isinstance(item, AudioEvent):
                            result.events.append(item)
                else:
                    for item in outputs:
                        from .types import AcousticLabel
                        if isinstance(item, AcousticLabel):
                            result.acoustic_labels.append(item)

        return result

    async def _safe_process(self, head, head_name: str, embedding):
        logger.debug("Running head: %s", head_name)
        return await head.process(embedding)
