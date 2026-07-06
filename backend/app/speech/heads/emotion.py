import random

from ..types import AcousticEmbedding, AcousticLabel
from .base import BaseHead, HeadOutput

LABELS = ["neutral", "happy", "sad", "angry", "surprised"]

# Roughly realistic distribution from conversational speech
_WEIGHTS = [0.50, 0.15, 0.10, 0.10, 0.15]


class EmotionHead(BaseHead):
    name = "emotion"

    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        label = random.choices(LABELS, weights=_WEIGHTS, k=1)[0]
        confidence = round(random.uniform(0.4, 0.95), 4)
        return [
            AcousticLabel(
                head=self.name,
                label=label,
                confidence=confidence,
                metadata={
                    "energy": round(random.uniform(0.0, 1.0), 4),
                    "embedding_dims": embedding.dims,
                },
            )
        ]
