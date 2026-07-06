import random

from ..types import AcousticEmbedding, AcousticLabel
from .base import BaseHead, HeadOutput

LABELS = ["low", "moderate", "high"]
_WEIGHTS = [0.50, 0.35, 0.15]


class StressHead(BaseHead):
    name = "stress"

    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        label = random.choices(LABELS, weights=_WEIGHTS, k=1)[0]
        confidence = round(random.uniform(0.5, 0.95), 4)
        return [
            AcousticLabel(
                head=self.name,
                label=label,
                confidence=confidence,
                metadata={
                    "pitch_range_estimate": round(random.uniform(50.0, 300.0), 1),
                    "intensity_estimate": round(random.uniform(0.2, 1.0), 4),
                },
            )
        ]
