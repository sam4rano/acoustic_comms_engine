import random

from ..types import AcousticEmbedding, AudioEvent
from .base import BaseHead, HeadOutput

EVENT_TYPES = ["laughter", "overlap", "long_pause", "filler", "cough", "silence"]
_EVENT_WEIGHTS = [0.10, 0.10, 0.15, 0.25, 0.10, 0.30]


class EventHead(BaseHead):
    name = "event"

    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        duration_ms = int((len(embedding.vector) / embedding.dims) * 5000)
        event_count = random.randint(0, 3)

        events: list[HeadOutput] = []
        for _ in range(event_count):
            etype = random.choices(EVENT_TYPES, weights=_EVENT_WEIGHTS, k=1)[0]
            start = random.randint(0, max(1, duration_ms - 200))
            end = min(start + random.randint(100, 800), duration_ms)
            events.append(
                AudioEvent(
                    event_type=etype,
                    start_ms=start,
                    end_ms=end,
                    confidence=round(random.uniform(0.5, 0.99), 4),
                )
            )

        events.sort(key=lambda e: e.start_ms)
        return events
