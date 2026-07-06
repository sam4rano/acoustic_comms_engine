from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.memory.backends.pg_fulltext import PostgresFullTextBackend
from app.memory.backends.qdrant import QdrantBackend
from app.memory.backends.redis_cache import RedisCache
from app.memory.service import MemoryService
from app.memory.types import MemoryDocument, MemoryQuery, SessionSummary


@pytest.fixture
def mock_qdrant_backend():
    backend = MagicMock(spec=QdrantBackend)
    backend.search = AsyncMock()
    backend.store = AsyncMock()
    backend.delete = AsyncMock()
    backend.health = AsyncMock(return_value=True)
    return backend


@pytest.fixture
def mock_pg_backend():
    backend = MagicMock(spec=PostgresFullTextBackend)
    backend.search = AsyncMock()
    backend.store = AsyncMock()
    backend.delete = AsyncMock()
    backend.health = AsyncMock(return_value=True)
    return backend


@pytest.fixture
def mock_redis_cache():
    cache = MagicMock(spec=RedisCache)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.invalidate = AsyncMock()
    cache.health = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def memory_service(mock_qdrant_backend, mock_pg_backend, mock_redis_cache):
    return MemoryService(
        qdrant=mock_qdrant_backend,
        pg=mock_pg_backend,
        redis=mock_redis_cache,
    )


@pytest.fixture
def sample_memory_query():
    return MemoryQuery(
        text="communication strategies for remote teams",
        user_id=uuid4(),
        top_k=5,
        threshold=0.6,
    )


@pytest.fixture
def sample_memory_document():
    return MemoryDocument(
        id=uuid4(),
        title="Remote Team Communication",
        content="Best practices for distributed team collaboration and async communication.",
        user_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        score=0.92,
        metadata={"source": "knowledge_base", "tags": ["remote", "async"]},
    )


@pytest.fixture
def sample_session_summaries():
    user_id = uuid4()
    return [
        SessionSummary(
            session_id=uuid4(),
            user_id=user_id,
            started_at=datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            duration_s=540,
            turn_count=24,
            language="en",
            overall_score=78.5,
            labels=["coaching", "sales"],
        ),
        SessionSummary(
            session_id=uuid4(),
            user_id=user_id,
            started_at=datetime(2026, 6, 2, 14, 0, 0, tzinfo=timezone.utc),
            duration_s=320,
            turn_count=15,
            language="en",
            overall_score=82.0,
            labels=["feedback"],
        ),
    ]
