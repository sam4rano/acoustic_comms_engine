import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.streaming.errors import SessionLimitError, SessionNotFoundError
from app.streaming.types import StreamSessionConfig, StreamSessionState

logger = logging.getLogger(__name__)


class StreamSessionManager:
    """Manages all active WebSocket streaming sessions.

    Thread-safe for async usage via an ``asyncio.Lock`` protecting
    shared dict access.  Sessions that produce no frames for longer
    than ``session_timeout_s`` are automatically evicted.
    """

    def __init__(
        self,
        max_sessions: int = 50,
        session_timeout_s: float = 30.0,
    ) -> None:
        self._max_sessions = max_sessions
        self._session_timeout_s = session_timeout_s
        self._sessions: dict[UUID, StreamSessionState] = {}
        self._lock = asyncio.Lock()
        self._total_frames_processed: int = 0
        self._total_errors: int = 0

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
            return state

    async def get_session(
        self, session_id: UUID
    ) -> Optional[StreamSessionState]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def update_state(
        self, session_id: UUID, status: str
    ) -> None:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError(f"Session {session_id} not found")
            state.status = status  # type: ignore[assignment]

    async def remove_session(self, session_id: UUID) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
            logger.info("Session removed: %s", session_id)

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
        return len(stale)
