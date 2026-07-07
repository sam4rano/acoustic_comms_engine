import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.memory.backends.redis_cache import RedisCache
from app.streaming.errors import SessionLimitError, SessionNotFoundError
from app.streaming.types import StreamSessionConfig, StreamSessionState

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "stream:session:"
_REDIS_TTL_S = 3600


class StreamSessionManager:
    """Manages all active WebSocket streaming sessions.

    Thread-safe for async usage via an ``asyncio.Lock`` protecting
    shared dict access.  Sessions that produce no frames for longer
    than ``session_timeout_s`` are automatically evicted.

    When a ``RedisCache`` is provided, session metadata is persisted to
    Redis as a backup.  On ``get_session``, if a session is not found in
    the in-memory dict, Redis is checked — this provides cross-process /
    restart resilience.
    """

    def __init__(
        self,
        max_sessions: int = 50,
        session_timeout_s: float = 30.0,
        redis: RedisCache | None = None,
    ) -> None:
        self._max_sessions = max_sessions
        self._session_timeout_s = session_timeout_s
        self._sessions: dict[UUID, StreamSessionState] = {}
        self._lock = asyncio.Lock()
        self._total_frames_processed: int = 0
        self._total_errors: int = 0
        self._redis = redis

    async def create_session(
        self, session_id: UUID, config: StreamSessionConfig
    ) -> StreamSessionState:
        async with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise SessionLimitError(
                    f"Max sessions ({self._max_sessions}) reached"
                )
            state = StreamSessionState(
                config=config,
                status="connecting",
                connected_at=datetime.now(timezone.utc),
            )
            self._sessions[session_id] = state
            logger.info("Session created: %s", session_id)

        await self._persist_to_redis(session_id, state)
        return state

    async def get_session(
        self, session_id: UUID
    ) -> Optional[StreamSessionState]:
        async with self._lock:
            session = self._sessions.get(session_id)
        if session is not None:
            return session
        return await self._restore_from_redis(session_id)

    async def update_state(
        self, session_id: UUID, status: str
    ) -> None:
        state: StreamSessionState | None = None
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError(f"Session {session_id} not found")
            state.status = status  # type: ignore[assignment]

        if state is not None:
            await self._persist_to_redis(session_id, state)

    async def remove_session(self, session_id: UUID) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
        logger.info("Session removed: %s", session_id)
        await self._remove_from_redis(session_id)

    async def get_active_sessions(self) -> list[StreamSessionState]:
        async with self._lock:
            return list(self._sessions.values())

    async def get_stats(self) -> dict:
        async with self._lock:
            active = sum(
                1 for s in self._sessions.values()
                if s.status in ("connecting", "active", "paused")
            )
            return {
                "active_sessions": active,
                "total_sessions": len(self._sessions),
                "total_frames_processed": self._total_frames_processed,
                "total_errors": self._total_errors,
                "max_sessions": self._max_sessions,
                "session_timeout_s": self._session_timeout_s,
            }

    async def increment_frames(self, session_id: UUID, count: int = 1) -> None:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is not None:
                state.frame_count += count
                state.last_frame_at = datetime.now(timezone.utc)
            self._total_frames_processed += count

    async def increment_errors(self, session_id: UUID) -> None:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is not None:
                state.error_count += 1
            self._total_errors += 1

    async def evict_stale_sessions(self) -> int:
        """Close sessions that have not received frames in ``session_timeout_s``.

        Returns the number of sessions evicted.
        """
        now = datetime.now(timezone.utc)
        stale: list[UUID] = []
        async with self._lock:
            for sid, state in self._sessions.items():
                if state.status == "closed":
                    stale.append(sid)
                    continue
                if state.last_frame_at is not None:
                    elapsed = (now - state.last_frame_at).total_seconds()
                    if elapsed > self._session_timeout_s:
                        state.status = "closed"
                        stale.append(sid)
            for sid in stale:
                self._sessions.pop(sid, None)
        if stale:
            logger.info("Evicted %d stale session(s)", len(stale))
        for sid in stale:
            await self._remove_from_redis(sid)
        return len(stale)

    # ── Redis persistence helpers ──────────────────────────────────

    def _session_to_dict(self, state: StreamSessionState) -> dict:
        return {
            "config": {
                "user_id": str(state.config.user_id),
                "session_id": str(state.config.session_id),
                "sample_rate": state.config.sample_rate,
                "enabled_heads": state.config.enabled_heads,
                "language": state.config.language,
                "vad_enabled": state.config.vad_enabled,
                "denoise_enabled": state.config.denoise_enabled,
            },
            "status": state.status,
            "connected_at": state.connected_at.isoformat(),
            "frame_count": state.frame_count,
            "last_frame_at": state.last_frame_at.isoformat() if state.last_frame_at else None,
            "error_count": state.error_count,
        }

    def _dict_to_session(self, data: dict) -> StreamSessionState:
        cfg = data["config"]
        return StreamSessionState(
            config=StreamSessionConfig(
                user_id=UUID(cfg["user_id"]),
                session_id=UUID(cfg["session_id"]),
                sample_rate=cfg.get("sample_rate", 16000),
                enabled_heads=cfg.get("enabled_heads", ["asr"]),
                language=cfg.get("language", "en"),
                vad_enabled=cfg.get("vad_enabled", True),
                denoise_enabled=cfg.get("denoise_enabled", False),
            ),
            status=data["status"],
            connected_at=datetime.fromisoformat(data["connected_at"]),
            frame_count=data.get("frame_count", 0),
            last_frame_at=(
                datetime.fromisoformat(data["last_frame_at"])
                if data.get("last_frame_at") else None
            ),
            error_count=data.get("error_count", 0),
        )

    async def _persist_to_redis(self, session_id: UUID, state: StreamSessionState) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                f"{_REDIS_KEY_PREFIX}{session_id}",
                self._session_to_dict(state),
                ttl_s=_REDIS_TTL_S,
            )
        except Exception:
            logger.debug("Redis persist skipped for session %s", session_id)

    async def _restore_from_redis(self, session_id: UUID) -> StreamSessionState | None:
        if self._redis is None:
            return None
        try:
            data = await self._redis.get(f"{_REDIS_KEY_PREFIX}{session_id}")
            if data is None:
                return None
            state = self._dict_to_session(data)
            async with self._lock:
                self._sessions[session_id] = state
            logger.info("Session restored from Redis: %s", session_id)
            return state
        except Exception:
            return None

    async def _remove_from_redis(self, session_id: UUID) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.invalidate(f"{_REDIS_KEY_PREFIX}{session_id}")
        except Exception:
            logger.debug("Redis remove skipped for session %s", session_id)
