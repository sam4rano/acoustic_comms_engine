import logging
from uuid import UUID

from app.memory.backends.base import MemoryBackend
from app.memory.errors import QdrantUnavailableError
from app.memory.types import MemoryDocument, MemoryQuery

logger = logging.getLogger(__name__)


class QdrantBackend(MemoryBackend):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "memory_documents",
        vector_size: int = 384,
        grpc_port: int = 6334,
        prefer_grpc: bool = False,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.grpc_port = grpc_port
        self.prefer_grpc = prefer_grpc
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient as _QdrantClient

            self._client = _QdrantClient(
                host=self.host,
                port=self.port,
                grpc_port=self.grpc_port,
                prefer_grpc=self.prefer_grpc,
            )
        return self._client

    async def search(self, query: MemoryQuery) -> list[MemoryDocument]:
        try:
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue

            filter_conditions = []
            if query.head:
                filter_conditions.append(
                    FieldCondition(
                        key="head",
                        match=MatchValue(value=query.head),
                    )
                )

            search_result = await self._async_search(
                query.text,
                limit=query.top_k,
                score_threshold=query.threshold,
                query_filter=Filter(
                    must=filter_conditions if filter_conditions else None
                ),
            )

            documents = []
            for scored_point in search_result:
                payload = scored_point.payload or {}
                documents.append(
                    MemoryDocument(
                        id=UUID(payload.get("id", "")),
                        title=payload.get("title", ""),
                        content=payload.get("content", ""),
                        user_id=UUID(payload.get("user_id", "")),
                        created_at=payload.get("created_at"),
                        score=scored_point.score,
                        metadata=payload.get("metadata", {}),
                    )
                )
            return documents

        except Exception as e:
            logger.warning("Qdrant search failed: %s", e)
            raise QdrantUnavailableError(f"Qdrant search failed: {e}") from e

    async def store(self, document: MemoryDocument) -> None:
        try:
            from qdrant_client.http.models import PointStruct

            point = PointStruct(
                id=str(document.id),
                vector=[0.0] * self.vector_size,
                payload={
                    "id": str(document.id),
                    "title": document.title,
                    "content": document.content,
                    "user_id": str(document.user_id),
                    "created_at": document.created_at.isoformat()
                    if document.created_at
                    else None,
                    "metadata": document.metadata,
                },
            )
            self.client.upsert(collection_name=self.collection_name, points=[point])

        except Exception as e:
            logger.warning("Qdrant store failed: %s", e)
            raise QdrantUnavailableError(f"Qdrant store failed: {e}") from e

    async def delete(self, document_id: UUID) -> None:
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[str(document_id)],
            )
        except Exception as e:
            logger.warning("Qdrant delete failed: %s", e)
            raise QdrantUnavailableError(f"Qdrant delete failed: {e}") from e

    async def health(self) -> bool:
        try:
            from qdrant_client.http.models import CollectionInfo

            info = self.client.get_collection(collection_name=self.collection_name)
            return info is not None
        except Exception:
            return False

    async def _async_search(self, text: str, limit: int, score_threshold: float, query_filter):
        loop = self._get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.search(
                collection_name=self.collection_name,
                query_vector=[0.0] * self.vector_size,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
            ),
        )

    @staticmethod
    def _get_event_loop():
        import asyncio

        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.new_event_loop()
