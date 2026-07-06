from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.streaming.dispatcher import StreamDispatcher
from app.streaming.manager import StreamSessionManager
from app.streaming.router import get_dispatcher, get_manager
from app.streaming.types import StreamMessage, StreamSessionConfig


@pytest.fixture(autouse=True)
def _setup_router_deps() -> tuple[StreamSessionManager, AsyncMock]:
    """Override streaming dependencies in the app."""
    manager = StreamSessionManager(max_sessions=10)
    dispatcher = AsyncMock(spec=StreamDispatcher)
    dispatcher.handle_start.return_value = StreamMessage(
        type="state_change", payload={"status": "active"}
    )
    dispatcher.handle_end.return_value = StreamMessage(
        type="state_change", payload={"status": "closing"}
    )
    dispatcher.handle_frame.return_value = []

    app.dependency_overrides[get_manager] = lambda: manager
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher

    yield manager, dispatcher

    app.dependency_overrides.pop(get_manager, None)
    app.dependency_overrides.pop(get_dispatcher, None)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


class TestStreamingRouter:
    """Tests for the /streaming HTTP endpoints."""

    async def test_list_sessions_returns_list(
        self, _setup_router_deps
    ) -> None:
        manager, _ = _setup_router_deps
        sid = uuid4()
        cfg = StreamSessionConfig(user_id=uuid4(), session_id=sid)
        await manager.create_session(sid, cfg)
        await manager.update_state(sid, "active")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/streaming/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert any(s["session_id"] == str(sid) for s in data)

    async def test_list_sessions_returns_empty_when_no_active(
        self, _setup_router_deps
    ) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/streaming/sessions")
            assert resp.status_code == 200
            assert resp.json() == []

    async def test_get_stats_returns_dict(
        self, _setup_router_deps
    ) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/streaming/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "active_sessions" in data
            assert "total_frames_processed" in data
            assert "max_sessions" in data

    async def test_close_session_works(
        self, _setup_router_deps
    ) -> None:
        manager, _ = _setup_router_deps
        sid = uuid4()
        cfg = StreamSessionConfig(user_id=uuid4(), session_id=sid)
        await manager.create_session(sid, cfg)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/streaming/sessions/{sid}/close")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "closed"

    async def test_close_session_returns_404_for_missing(
        self, _setup_router_deps
    ) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/streaming/sessions/{uuid4()}/close")
            assert resp.status_code == 404

    def test_websocket_endpoint_accepts_connection(
        self, test_client: TestClient, _setup_router_deps
    ) -> None:
        session_id = str(uuid4())
        with test_client.websocket_connect(f"/streaming/ws/{session_id}") as ws:
            ws.send_json({
                "type": "start_session",
                "payload": {
                    "user_id": str(uuid4()),
                    "session_id": session_id,
                    "sample_rate": 16000,
                    "language": "en",
                },
            })
            resp = ws.receive_json()
            assert resp["type"] == "state_change"
