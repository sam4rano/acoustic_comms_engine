from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.memory.backends.pg_fulltext import PostgresFullTextBackend
from app.memory.backends.qdrant import QdrantBackend
from app.memory.backends.redis_cache import RedisCache
from app.memory.errors import BackendUnavailableError, PostgresUnavailableError, QdrantUnavailableError
from app.memory.service import AnalysisConfig, MemoryService
from app.memory.types import MemoryDocument, MemoryQuery, RetrievalBundle


class TestMemoryService:
    async def test_build_context_returns_bundle(
        self, memory_service, mock_qdrant_backend, mock_pg_backend
    ):
        session_id = uuid4()
        user_id = uuid4()
        doc = MemoryDocument(
            id=uuid4(),
            title="Doc",
            content="Content",
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            score=0.85,
        )
        mock_qdrant_backend.search.return_value = [doc]

        bundle = await memory_service.build_context(session_id, user_id)

        assert isinstance(bundle, RetrievalBundle)
        assert len(bundle.documents) == 1
        assert bundle.documents[0].title == "Doc"
        assert bundle.metadata["session_id"] == str(session_id)

    async def test_search_returns_memory_result(
        self, memory_service, mock_qdrant_backend, sample_memory_query
    ):
        doc = MemoryDocument(
            id=uuid4(),
            title="Result",
            content="Content",
            user_id=sample_memory_query.user_id,
            created_at=datetime.now(timezone.utc),
            score=0.9,
        )
        mock_qdrant_backend.search.return_value = [doc]

        result = await memory_service.search(sample_memory_query)

        assert len(result.documents) == 1
        assert result.documents[0].title == "Result"
        assert result.query == sample_memory_query
        assert result.source in ("hybrid", "qdrant")
        assert result.retrieval_time_ms >= 0

    async def test_search_falls_back_to_pg_when_qdrant_insufficient(
        self, memory_service, mock_qdrant_backend, mock_pg_backend, sample_memory_query
    ):
        mock_qdrant_backend.search.return_value = []

        pg_doc = MemoryDocument(
            id=uuid4(),
            title="PG Fallback",
            content="From PostgreSQL",
            user_id=sample_memory_query.user_id,
            created_at=datetime.now(timezone.utc),
        )
        mock_pg_backend.search.return_value = [pg_doc]

        result = await memory_service.search(sample_memory_query)

        assert len(result.documents) == 1
        assert result.documents[0].title == "PG Fallback"
        mock_pg_backend.search.assert_awaited_once()

    async def test_search_falls_back_to_pg_when_qdrant_unavailable(
        self, memory_service, mock_qdrant_backend, mock_pg_backend, sample_memory_query
    ):
        mock_qdrant_backend.search.side_effect = QdrantUnavailableError("Qdrant down")

        pg_doc = MemoryDocument(
            id=uuid4(),
            title="PG Fallback",
            content="From PostgreSQL",
            user_id=sample_memory_query.user_id,
            created_at=datetime.now(timezone.utc),
        )
        mock_pg_backend.search.return_value = [pg_doc]

        result = await memory_service.search(sample_memory_query)

        assert len(result.documents) == 1
        assert result.source == "pg_fulltext"

    async def test_search_caches_results(
        self, memory_service, mock_qdrant_backend, mock_redis_cache, sample_memory_query
    ):
        doc = MemoryDocument(
            id=uuid4(),
            title="Cached",
            content="Content",
            user_id=sample_memory_query.user_id,
            created_at=datetime.now(timezone.utc),
            score=0.9,
        )
        mock_qdrant_backend.search.return_value = [doc]

        result = await memory_service.search(sample_memory_query)

        mock_redis_cache.set.assert_awaited_once()
        args, kwargs = mock_redis_cache.set.call_args
        assert "memory:search:" in args[0]

    async def test_search_uses_cache_on_subsequent_calls(
        self, memory_service, mock_redis_cache, sample_memory_query
    ):
        cached_doc = MemoryDocument(
            id=uuid4(),
            title="Cached Result",
            content="From cache",
            user_id=sample_memory_query.user_id,
            created_at=datetime.now(timezone.utc),
        )
        mock_redis_cache.get.return_value = {
            "documents": [
                {
                    "id": str(cached_doc.id),
                    "title": cached_doc.title,
                    "content": cached_doc.content,
                    "user_id": str(cached_doc.user_id),
                    "created_at": cached_doc.created_at.isoformat(),
                    "score": None,
                    "metadata": {},
                }
            ]
        }

        result = await memory_service.search(sample_memory_query)

        assert len(result.documents) == 1
        assert result.documents[0].title == "Cached Result"
        assert result.source == "cache"

    async def test_store_document_stores_in_both_backends(
        self, memory_service, mock_qdrant_backend, mock_pg_backend, sample_memory_document
    ):
        await memory_service.store_document(sample_memory_document)

        mock_qdrant_backend.store.assert_awaited_once_with(sample_memory_document)
        mock_pg_backend.store.assert_awaited_once_with(sample_memory_document)

    async def test_store_document_invalidates_cache(
        self, memory_service, mock_redis_cache, sample_memory_document
    ):
        await memory_service.store_document(sample_memory_document)

        mock_redis_cache.invalidate.assert_awaited_once_with(
            f"memory:search:{sample_memory_document.user_id}:"
        )

    async def test_store_document_raises_when_both_fail(
        self, memory_service, mock_qdrant_backend, mock_pg_backend, sample_memory_document
    ):
        mock_qdrant_backend.store.side_effect = QdrantUnavailableError("Qdrant down")
        mock_pg_backend.store.side_effect = PostgresUnavailableError("PG down")

        with pytest.raises(BackendUnavailableError):
            await memory_service.store_document(sample_memory_document)

    async def test_graceful_degradation_when_qdrant_unavailable(
        self, memory_service, mock_qdrant_backend, mock_pg_backend
    ):
        session_id = uuid4()
        user_id = uuid4()
        mock_qdrant_backend.search.side_effect = QdrantUnavailableError("Qdrant down")

        pg_doc = MemoryDocument(
            id=uuid4(),
            title="PG Fallback",
            content="PG content",
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )
        mock_pg_backend.search.return_value = [pg_doc]

        bundle = await memory_service.build_context(session_id, user_id)

        assert len(bundle.documents) == 1
        assert bundle.documents[0].title == "PG Fallback"

    async def test_graceful_degradation_when_pg_unavailable(
        self, memory_service, mock_qdrant_backend, mock_pg_backend
    ):
        session_id = uuid4()
        user_id = uuid4()
        doc = MemoryDocument(
            id=uuid4(),
            title="Qdrant Only",
            content="Qdrant content",
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            score=0.85,
        )
        mock_qdrant_backend.search.return_value = [doc]
        mock_pg_backend.search.side_effect = Exception("PG down")

        bundle = await memory_service.build_context(session_id, user_id)

        assert len(bundle.documents) == 1
        assert bundle.documents[0].title == "Qdrant Only"

    async def test_build_context_with_empty_results(
        self, memory_service, mock_qdrant_backend, mock_pg_backend
    ):
        session_id = uuid4()
        user_id = uuid4()
        mock_qdrant_backend.search.return_value = []
        mock_pg_backend.search.return_value = []

        bundle = await memory_service.build_context(session_id, user_id)

        assert len(bundle.documents) == 0
        assert len(bundle.prior_sessions) == 0
        assert isinstance(bundle, RetrievalBundle)

    async def test_build_context_with_config(
        self, memory_service, mock_qdrant_backend
    ):
        session_id = uuid4()
        user_id = uuid4()
        mock_qdrant_backend.search.return_value = []

        config = AnalysisConfig(
            focus="empathy",
            enabled_heads=["asr", "emotion"],
            include_prior_sessions=False,
        )
        bundle = await memory_service.build_context(session_id, user_id, config)

        assert bundle.metadata["session_id"] == str(session_id)

    async def test_search_with_custom_config(
        self, memory_service, mock_qdrant_backend, mock_redis_cache
    ):
        memory_service.config.cache_ttl_s = 60
        memory_service.config.top_k_turns = 3

        doc = MemoryDocument(
            id=uuid4(),
            title="Config Test",
            content="Testing config",
            user_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            score=0.8,
        )
        mock_qdrant_backend.search.return_value = [doc]

        query = MemoryQuery(text="test", user_id=uuid4(), top_k=3)
        result = await memory_service.search(query)

        assert len(result.documents) == 1
        assert result.source in ("hybrid", "qdrant")
