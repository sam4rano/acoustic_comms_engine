import statistics
import random

from ..types import AcousticEmbedding, AcousticLabel
from .base import BaseHead, HeadOutput


class ProsodyHead(BaseHead):
    name = "prosody"

    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        variance = statistics.pvariance(embedding.vector) if len(embedding.vector) > 1 else 0.0

        if variance < 0.01:
            label = "flat"
        elif variance < 0.03:
            label = "monotone"
        elif variance < 0.06:
            label = "varied"
        else:
            label = "expressive"

        conf_base = min(variance / 0.08, 1.0)
        confidence = round(conf_base + random.uniform(-0.1, 0.1), 4)
        confidence = max(0.3, min(0.99, confidence))

        return [
            AcousticLabel(
                head=self.name,
                label=label,
                confidence=confidence,
                metadata={
                    "variance": round(variance, 6),
                    "mean": round(statistics.mean(embedding.vector), 6),
                },
            )
        ]
