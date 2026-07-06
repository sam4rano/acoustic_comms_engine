from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.memory.backends.qdrant import QdrantBackend
from app.memory.backends.pg_fulltext import PostgresFullTextBackend
from app.memory.backends.redis_cache import RedisCache
from app.memory.errors import QdrantUnavailableError, RedisUnavailableError
from app.memory.types import MemoryDocument, MemoryQuery


# ── QdrantBackend ──────────────────────────────────────────────────────────────


class TestQdrantBackend:
    @pytest.fixture
    def backend(self):
        return QdrantBackend(
            host="localhost",
            port=6333,
            collection_name="test_docs",
            vector_size=384,
        )

    @pytest.fixture
    def mock_client(self):
        with patch("qdrant_client.QdrantClient") as mock:
            yield mock

    async def test_search_returns_documents(self, backend, mock_client):
        fake_point = MagicMock()
        fake_point.score = 0.92
        fake_point.payload = {
            "id": str(uuid4()),
            "title": "Test Doc",
            "content": "Test content",
            "user_id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        }
        mock_client.return_value.search.return_value = [fake_point]

        query = MemoryQuery(text="test", user_id=uuid4(), top_k=10, threshold=0.5)
        results = await backend.search(query)

        assert len(results) == 1
        assert results[0].title == "Test Doc"
        assert results[0].score == 0.92

    async def test_store_upserts_correctly(self, backend, mock_client):
        doc = MemoryDocument(
            id=uuid4(),
            title="Store Test",
            content="Testing store",
            user_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        await backend.store(doc)

        mock_client.return_value.upsert.assert_called_once()
        kwargs = mock_client.return_value.upsert.call_args.kwargs
        assert kwargs["collection_name"] == "test_docs"
        assert len(kwargs["points"]) == 1

    async def test_health_check_returns_true(self, backend, mock_client):
        mock_client.return_value.get_collection.return_value = MagicMock()
        assert await backend.health() is True

    async def test_health_check_returns_false_on_error(self, backend, mock_client):
        mock_client.return_value.get_collection.side_effect = Exception("Connection failed")
        assert await backend.health() is False

    async def test_search_raises_qdrant_unavailable(self, backend, mock_client):
        mock_client.return_value.search.side_effect = Exception("Connection refused")

        query = MemoryQuery(text="test", user_id=uuid4(), top_k=5)
        with pytest.raises(QdrantUnavailableError):
            await backend.search(query)

    async def test_store_raises_qdrant_unavailable(self, backend, mock_client):
        mock_client.return_value.upsert.side_effect = Exception("Connection refused")

        doc = MemoryDocument(
            id=uuid4(),
            title="Fail",
            content="Fail",
            user_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(QdrantUnavailableError):
            await backend.store(doc)

    async def test_delete_calls_qdrant(self, backend, mock_client):
        doc_id = uuid4()
        await backend.delete(doc_id)

        mock_client.return_value.delete.assert_called_once()
        kwargs = mock_client.return_value.delete.call_args.kwargs
        assert kwargs["collection_name"] == "test_docs"

    async def test_delete_raises_qdrant_unavailable(self, backend, mock_client):
        mock_client.return_value.delete.side_effect = Exception("Connection refused")

        with pytest.raises(QdrantUnavailableError):
            await backend.delete(uuid4())


# ── PostgresFullTextBackend ────────────────────────────────────────────────────


class TestPostgresFullTextBackend:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        factory.return_value.__aexit__ = AsyncMock(return_value=None)
        return factory

    @pytest.fixture
    def backend(self, mock_session_factory):
        return PostgresFullTextBackend(session_factory=mock_session_factory)

    async def test_search_returns_documents(self, backend, mock_session):
        fake_row = MagicMock()
        fake_row.id = uuid4()
        fake_row.title = "PG Doc"
        fake_row.content = "PostgreSQL content"
        fake_row.user_id = uuid4()
        fake_row.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [fake_row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        query = MemoryQuery(text="pg test", user_id=uuid4(), top_k=5)
        results = await backend.search(query)

        assert len(results) == 1
        assert results[0].title == "PG Doc"

    async def test_store_inserts_correctly(self, backend, mock_session):
        mock_session.get = AsyncMock(return_value=None)

        doc = MemoryDocument(
            id=uuid4(),
            title="PG Store",
            content="Store test",
            user_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        await backend.store(doc)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    async def test_store_updates_existing(self, backend, mock_session):
        existing = MagicMock()
        existing.title = "Old Title"
        existing.content = "Old content"
        mock_session.get = AsyncMock(return_value=existing)

        doc = MemoryDocument(
            id=uuid4(),
            title="Updated Title",
            content="Updated content",
            user_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        await backend.store(doc)
        assert existing.title == "Updated Title"
        assert existing.content == "Updated content"
        mock_session.commit.assert_awaited_once()

    async def test_delete_removes_document(self, backend, mock_session):
        existing = MagicMock()
        mock_session.get = AsyncMock(return_value=existing)

        await backend.delete(uuid4())
        mock_session.delete.assert_called_once_with(existing)
        mock_session.commit.assert_awaited_once()

    async def test_health_check(self, backend, mock_session):
        result = await backend.health()
        assert result is True

    async def test_health_check_failure(self, backend, mock_session):
        mock_session.execute = AsyncMock(side_effect=Exception("DB down"))
        result = await backend.health()
        assert result is False


# ── RedisCache ─────────────────────────────────────────────────────────────────


class TestRedisCache:
    @pytest.fixture
    def mock_redis(self):
        with patch("redis.asyncio.Redis") as mock:
            instance = mock.return_value
            instance.get = AsyncMock()
            instance.set = AsyncMock()
            instance.scan = AsyncMock()
            instance.delete = AsyncMock()
            instance.ping = AsyncMock(return_value=True)
            yield instance

    @pytest.fixture
    def cache(self):
        return RedisCache(host="localhost", port=6379, db=0)

    async def test_get_returns_value(self, cache, mock_redis):
        mock_redis.get.return_value = '{"key": "value"}'
        result = await cache.get("test-key")
        assert result == {"key": "value"}

    async def test_get_returns_none_when_missing(self, cache, mock_redis):
        mock_redis.get.return_value = None
        result = await cache.get("missing")
        assert result is None

    async def test_set_stores_value(self, cache, mock_redis):
        await cache.set("test-key", {"data": 123}, ttl_s=60)
        mock_redis.set.assert_called_once_with(
            "test-key", '{"data": 123}', ex=60
        )

    async def test_set_default_ttl(self, cache, mock_redis):
        await cache.set("test-key", {"data": 123})
        mock_redis.set.assert_called_once_with(
            "test-key", '{"data": 123}', ex=300
        )

    async def test_invalidate_clears_prefix(self, cache, mock_redis):
        mock_redis.scan.return_value = (0, ["key:1", "key:2"])
        await cache.invalidate("prefix:")
        mock_redis.delete.assert_called_once_with("key:1", "key:2")

    async def test_invalidate_multiple_pages(self, cache, mock_redis):
        mock_redis.scan.side_effect = [
            (1, ["key:1"]),
            (0, ["key:2"]),
        ]
        await cache.invalidate("prefix:")
        assert mock_redis.delete.call_count == 2

    async def test_get_raises_on_connection_error(self, cache, mock_redis):
        mock_redis.get.side_effect = Exception("Connection refused")
        with pytest.raises(RedisUnavailableError):
            await cache.get("fail")

    async def test_set_raises_on_connection_error(self, cache, mock_redis):
        mock_redis.set.side_effect = Exception("Connection refused")
        with pytest.raises(RedisUnavailableError):
            await cache.set("fail", {})

    async def test_health_returns_true(self, cache, mock_redis):
        assert await cache.health() is True

    async def test_health_returns_false_on_error(self, cache, mock_redis):
        mock_redis.ping.side_effect = Exception("Down")
        assert await cache.health() is False
