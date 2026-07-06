from abc import ABC, abstractmethod
from typing import Union

from ..types import AcousticEmbedding, AcousticLabel, AudioEvent

HeadOutput = Union[AcousticLabel, AudioEvent]


class BaseHead(ABC):
    name: str

    @abstractmethod
    async def process(self, embedding: AcousticEmbedding) -> list[HeadOutput]:
        ...
