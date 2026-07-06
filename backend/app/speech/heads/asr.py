import math

from ..types import AcousticEmbedding, TranscriptSegment
from .base import BaseHead, HeadOutput


class ASRHead(BaseHead):
    name = "asr"

    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        duration_ms = int(math.sqrt(embedding.dims) * 30)
        return [
            TranscriptSegment(
                text=f"[transcript for {embedding.encoder_version} embedding]",
                start_ms=0,
                end_ms=duration_ms,
                confidence=0.85,
                is_partial=False,
            )
        ]
