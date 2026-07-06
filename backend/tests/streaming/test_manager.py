import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.streaming.errors import SessionLimitError, SessionNotFoundError
from app.streaming.manager import StreamSessionManager
from app.streaming.types import StreamSessionConfig


class TestStreamSessionManager:
    """Tests for ``StreamSessionManager``."""

    async def test_create_session_returns_correct_state(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        state = await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        assert state.config == sample_stream_config
        assert state.status == "connecting"
        assert state.frame_count == 0
        assert state.error_count == 0
        assert isinstance(state.connected_at, datetime)

    async def test_get_session_finds_by_id(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is not None
        assert state.config.session_id == sample_stream_config.session_id

    async def test_get_session_returns_none_for_missing(
        self, mock_manager: StreamSessionManager
    ) -> None:
        state = await mock_manager.get_session(uuid4())
        assert state is None

    async def test_remove_session_cleans_up(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.remove_session(sample_stream_config.session_id)
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is None

    async def test_get_active_sessions_returns_correct_count(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        cfg2 = StreamSessionConfig(user_id=uuid4(), session_id=uuid4())
        await mock_manager.create_session(sample_stream_config.session_id, sample_stream_config)
        await mock_manager.create_session(cfg2.session_id, cfg2)
        sessions = await mock_manager.get_active_sessions()
        assert len(sessions) == 2

    async def test_session_timeout_evicts_stale_sessions(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        mock_manager._session_timeout_s = 0.0
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.increment_frames(sample_stream_config.session_id)

        evicted = await mock_manager.evict_stale_sessions()
        assert evicted == 1
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is None

    async def test_session_timeout_respects_recent_frames(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        mock_manager._session_timeout_s = 3600.0
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.increment_frames(sample_stream_config.session_id)

        evicted = await mock_manager.evict_stale_sessions()
        assert evicted == 0
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is not None

    async def test_max_session_limit_raises_error(
        self, sample_stream_config: StreamSessionConfig
    ) -> None:
        manager = StreamSessionManager(max_sessions=2)
        await manager.create_session(uuid4(), sample_stream_config)
        await manager.create_session(uuid4(), sample_stream_config)
        with pytest.raises(SessionLimitError):
            await manager.create_session(uuid4(), sample_stream_config)

    async def test_update_state_transitions(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.update_state(sample_stream_config.session_id, "active")
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is not None
        assert state.status == "active"

    async def test_update_state_raises_on_missing(self) -> None:
        manager = StreamSessionManager()
        with pytest.raises(SessionNotFoundError):
            await manager.update_state(uuid4(), "active")

    async def test_increment_frames(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.increment_frames(sample_stream_config.session_id, count=5)
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is not None
        assert state.frame_count == 5
        assert state.last_frame_at is not None

    async def test_increment_errors(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.increment_errors(sample_stream_config.session_id)
        state = await mock_manager.get_session(sample_stream_config.session_id)
        assert state is not None
        assert state.error_count == 1

    async def test_get_stats(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        await mock_manager.create_session(
            sample_stream_config.session_id, sample_stream_config
        )
        await mock_manager.increment_frames(sample_stream_config.session_id, count=10)
        stats = await mock_manager.get_stats()
        assert stats["active_sessions"] == 1
        assert stats["total_frames_processed"] == 10
        assert stats["max_sessions"] == 10

    async def test_concurrent_access_safety(
        self, mock_manager: StreamSessionManager, sample_stream_config: StreamSessionConfig
    ) -> None:
        """Run multiple coroutines concurrently to verify thread-safety."""
        async def create_and_modify(sid):
            cfg = StreamSessionConfig(user_id=uuid4(), session_id=sid)
            await mock_manager.create_session(sid, cfg)
            for _ in range(10):
                await mock_manager.increment_frames(sid)
                await mock_manager.increment_errors(sid)
            return sid

        ids = [uuid4() for _ in range(5)]
        results = await asyncio.gather(*[create_and_modify(sid) for sid in ids])
        assert len(results) == 5
        sessions = await mock_manager.get_active_sessions()
        assert len(sessions) == 5
