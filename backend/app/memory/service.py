import logging
import time
from dataclasses import dataclass, field
from uuid import UUID
from typing import Optional

from app.memory.backends.pg_fulltext import PostgresFullTextBackend
from app.memory.backends.qdrant import QdrantBackend
from app.memory.backends.redis_cache import RedisCache
from app.memory.errors import (
    BackendUnavailableError,
    QdrantUnavailableError,
    PostgresUnavailableError,
)
from app.memory.types import (
    EmbeddingMatch,
    MemoryDocument,
    MemoryQuery,
    MemoryResult,
    RetrievalBundle,
    SessionSummary,
)

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "memory_documents"
    qdrant_vector_size: int = 384
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    cache_ttl_s: int = 300
    top_k_turns: int = 15
    acoustic_neighbors: int = 5
    include_prior_sessions: bool = True


@dataclass
class AnalysisConfig:
    focus: Optional[str] = None
    dimensions: Optional[list[str]] = None
    language: str = "en"
    enabled_heads: list[str] = field(
        default_factory=lambda: ["asr", "emotion", "prosody", "stress", "fluency"]
    )
    min_turn_confidence: float = 0.6
    include_prior_sessions: bool = True
    max_turns: int = 500


class MemoryService:
    def __init__(
        self,
        qdrant: Optional[QdrantBackend] = None,
        pg: Optional[PostgresFullTextBackend] = None,
        redis: Optional[RedisCache] = None,
        config: Optional[MemoryConfig] = None,
        pg_session_factory=None,
    ):
        self.config = config or MemoryConfig()
        self.qdrant = qdrant or QdrantBackend(
            host=self.config.qdrant_host,
            port=self.config.qdrant_port,
            collection_name=self.config.qdrant_collection,
            vector_size=self.config.qdrant_vector_size,
        )
        self.pg = pg or PostgresFullTextBackend(session_factory=pg_session_factory)
        self.redis = redis or RedisCache(
            host=self.config.redis_host,
            port=self.config.redis_port,
            db=self.config.redis_db,
        )

    async def build_context(
        self,
        session_id: UUID,
        user_id: UUID,
        config: Optional[AnalysisConfig] = None,
    ) -> RetrievalBundle:
        cfg = config or AnalysisConfig()
        bundle = RetrievalBundle(metadata={"session_id": str(session_id), "user_id": str(user_id)})

        # 1. Prior sessions
        if cfg.include_prior_sessions:
            try:
                bundle.prior_sessions = await self._get_prior_sessions(user_id, session_id)
            except PostgresUnavailableError:
                logger.warning("PG unavailable — skipping prior sessions")

        # 2. Relevant documents from Qdrant (text embeddings)
        try:
            text_query = MemoryQuery(
                text="",
                user_id=user_id,
                top_k=self.config.top_k_turns,
                threshold=cfg.min_turn_confidence,
            )
            bundle.documents = await self.qdrant.search(text_query)
        except QdrantUnavailableError:
            logger.warning("Qdrant unavailable — skipping document retrieval")

        # 3. Acoustic neighbors from Qdrant
        if set(cfg.enabled_heads) - {"asr"}:
            for head in cfg.enabled_heads:
                if head == "asr":
                    continue
                try:
                    acoustic_query = MemoryQuery(
                        text="",
                        user_id=user_id,
                        top_k=self.config.acoustic_neighbors,
                        threshold=0.0,
                        head=head,
                    )
                    results = await self.qdrant.search(acoustic_query)
                    embedding_ids = [r.id for r in results if r.score is not None]
                except QdrantUnavailableError:
                    logger.warning("Qdrant unavailable — skipping acoustic neighbors for %s", head)
                    embedding_ids = []
        else:
            embedding_ids = []

        # Attempt keyword fallback from PG if Qdrant was unavailable or returned nothing
        try:
            if not bundle.documents:
                pg_query = MemoryQuery(
                    text="",
                    user_id=user_id,
                    top_k=self.config.top_k_turns,
                    threshold=cfg.min_turn_confidence,
                )
                bundle.documents = await self.pg.search(pg_query)
        except PostgresUnavailableError:
            logger.warning("PG unavailable — skipping keyword fallback")

        bundle.metadata["retrieval_mode"] = "hybrid"
        return bundle

    async def search(self, query: MemoryQuery) -> MemoryResult:
        start = time.monotonic()
        cache_key = f"memory:search:{query.user_id}:{hash(query.text)}:{query.top_k}:{query.head}"

        # Check cache first
        try:
            cached = await self.redis.get(cache_key)
            if cached is not None:
                docs = [MemoryDocument(**d) for d in cached["documents"]]
                elapsed = (time.monotonic() - start) * 1000
                return MemoryResult(
                    documents=docs,
                    query=query,
                    retrieval_time_ms=elapsed,
                    source="cache",
                )
        except BackendUnavailableError:
            pass

        documents = []
        source = "hybrid"

        # Try Qdrant first
        try:
            documents = await self.qdrant.search(query)
        except QdrantUnavailableError:
            source = "pg_fulltext"

        # Fallback / supplement with PG full-text
        if len(documents) < query.top_k:
            try:
                pg_docs = await self.pg.search(query)
                seen_ids = {d.id for d in documents}
                documents.extend(d for d in pg_docs if d.id not in seen_ids)
            except PostgresUnavailableError:
                pass

        # Cache result
        try:
            await self.redis.set(
                cache_key,
                {"documents": [self._doc_to_dict(d) for d in documents]},
                ttl_s=self.config.cache_ttl_s,
            )
        except BackendUnavailableError:
            pass

        elapsed = (time.monotonic() - start) * 1000
        return MemoryResult(
            documents=documents[: query.top_k],
            query=query,
            retrieval_time_ms=elapsed,
            source=source,
        )

    async def store_document(self, document: MemoryDocument) -> None:
        exceptions = []

        try:
            await self.qdrant.store(document)
        except QdrantUnavailableError as e:
            exceptions.append(e)

        try:
            await self.pg.store(document)
        except PostgresUnavailableError as e:
            exceptions.append(e)

        if len(exceptions) == 2:
            raise BackendUnavailableError(
                f"Both Qdrant and PG failed to store document {document.id}: {exceptions}"
            )

        # Invalidate cache for this user
        try:
            await self.redis.invalidate(f"memory:search:{document.user_id}:")
        except BackendUnavailableError:
            pass

    async def _get_prior_sessions(
        self, user_id: UUID, exclude_session_id: UUID
    ) -> list[SessionSummary]:
        try:
            async with self.pg.session_factory() as session:
                from app.models.session import Session as ORMSession

                from sqlalchemy import select

                stmt = (
                    select(ORMSession)
                    .where(
                        ORMSession.user_id == user_id,
                        ORMSession.id != exclude_session_id,
                    )
                    .order_by(ORMSession.created_at.desc())
                    .limit(10)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

                summaries = []
                for row in rows:
                    duration = 0
                    if row.started_at and row.ended_at:
                        duration = int((row.ended_at - row.started_at).total_seconds())

                    summaries.append(
                        SessionSummary(
                            session_id=row.id,
                            user_id=row.user_id,
                            started_at=row.started_at or row.created_at,
                            duration_s=duration,
                            turn_count=len(row.turns) if hasattr(row, "turns") else 0,
                            language=row.language,
                            overall_score=None,
                            labels=[],
                        )
                    )
                return summaries
        except Exception as e:
            raise PostgresUnavailableError(
                f"Failed to retrieve prior sessions: {e}"
            ) from e

    @staticmethod
    def _doc_to_dict(doc: MemoryDocument) -> dict:
        return {
            "id": str(doc.id),
            "title": doc.title,
            "content": doc.content,
            "user_id": str(doc.user_id),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "score": doc.score,
            "metadata": doc.metadata,
        }
