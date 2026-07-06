from abc import ABC, abstractmethod
from uuid import UUID

from app.memory.types import MemoryDocument, MemoryQuery


class MemoryBackend(ABC):
    @abstractmethod
    async def search(self, query: MemoryQuery) -> list[MemoryDocument]:
        ...

    @abstractmethod
    async def store(self, document: MemoryDocument) -> None:
        ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...
