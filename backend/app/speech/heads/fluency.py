import random

from ..types import AcousticEmbedding, AcousticLabel
from .base import BaseHead, HeadOutput

LABELS = ["fluent", "some_disfluency", "disfluent"]
_WEIGHTS = [0.60, 0.30, 0.10]


class FluencyHead(BaseHead):
    name = "fluency"

    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        label = random.choices(LABELS, weights=_WEIGHTS, k=1)[0]
        confidence = round(random.uniform(0.4, 0.95), 4)
        return [
            AcousticLabel(
                head=self.name,
                label=label,
                confidence=confidence,
                metadata={
                    "filler_word_estimate": round(random.uniform(0.0, 5.0), 2),
                    "silence_ratio_estimate": round(random.uniform(0.0, 0.3), 4),
                },
            )
        ]
