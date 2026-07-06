import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status

from app.streaming.dispatcher import StreamDispatcher
from app.streaming.errors import SessionNotFoundError
from app.streaming.handler import handle_websocket
from app.streaming.manager import StreamSessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["streaming"])


def get_manager() -> StreamSessionManager:
    """Dependency provider for the session manager singleton."""
    from app.streaming.router import _manager
    return _manager


def get_dispatcher() -> StreamDispatcher:
    """Dependency provider for the dispatcher singleton."""
    from app.streaming.router import _dispatcher
    return _dispatcher


_manager: StreamSessionManager | None = None
_dispatcher: StreamDispatcher | None = None


def setup_streaming(
    manager: StreamSessionManager,
    dispatcher: StreamDispatcher,
) -> None:
    """Wire manager and dispatcher into the router module.

    Called once at application startup.
    """
    global _manager, _dispatcher
    _manager = manager
    _dispatcher = dispatcher


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    manager: StreamSessionManager = Depends(get_manager),
    dispatcher: StreamDispatcher = Depends(get_dispatcher),
) -> None:
    """WebSocket endpoint for real-time audio streaming.

    The client must send a ``start_session`` JSON message first,
    followed by binary audio frames or control messages.
    """
    await handle_websocket(websocket, manager, dispatcher)


@router.get("/sessions")
async def list_sessions(
    manager: StreamSessionManager = Depends(get_manager),
) -> list[dict]:
    """List all active sessions (for debugging / monitoring)."""
    sessions = await manager.get_active_sessions()
    return [
        {
            "session_id": str(s.config.session_id),
            "user_id": str(s.config.user_id),
            "status": s.status,
            "connected_at": s.connected_at.isoformat(),
            "frame_count": s.frame_count,
            "error_count": s.error_count,
            "language": s.config.language,
        }
        for s in sessions
    ]


@router.get("/stats")
async def get_stats(
    manager: StreamSessionManager = Depends(get_manager),
) -> dict:
    """Get stream statistics."""
    return await manager.get_stats()


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: UUID,
    manager: StreamSessionManager = Depends(get_manager),
) -> dict:
    """Force-close a streaming session."""
    session = await manager.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    await manager.update_state(session_id, "closed")
    await manager.remove_session(session_id)
    return {"status": "closed", "session_id": str(session_id)}
