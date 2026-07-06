from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.streaming.dispatcher import StreamDispatcher
from app.streaming.manager import StreamSessionManager
from app.streaming.router import get_dispatcher, get_manager
from app.streaming.types import StreamMessage, StreamSessionConfig


@pytest.fixture(autouse=True)
def _setup_handler_deps() -> tuple[StreamSessionManager, AsyncMock]:
    """Override streaming dependencies in the app with test instances."""
    manager = StreamSessionManager(max_sessions=10)
    dispatcher = AsyncMock(spec=StreamDispatcher)
    dispatcher.handle_start.return_value = StreamMessage(
        type="state_change",
        payload={"status": "active", "session_id": str(uuid4())},
    )
    dispatcher.handle_end.return_value = StreamMessage(
        type="state_change",
        payload={"status": "closing", "frames_processed": 0, "errors": 0},
    )
    dispatcher.handle_frame.return_value = []
    dispatcher.flush_pending.return_value = []

    app.dependency_overrides[get_manager] = lambda: manager
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher

    yield manager, dispatcher

    app.dependency_overrides.pop(get_manager, None)
    app.dependency_overrides.pop(get_dispatcher, None)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


class TestWebSocketHandler:
    """Tests for the WebSocket endpoint handler."""

    def test_connect_disconnect_lifecycle(
        self, test_client: TestClient, _setup_handler_deps
    ) -> None:
        manager, dispatcher = _setup_handler_deps
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

    def test_ping_pong_keepalive(
        self, test_client: TestClient, _setup_handler_deps
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
            ws.receive_json()  # ack

            ws.send_json({"type": "ping", "payload": {}})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_disconnect_cleanup(
        self, test_client: TestClient, _setup_handler_deps
    ) -> None:
        manager, dispatcher = _setup_handler_deps
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
            ws.receive_json()  # ack

        # After disconnect, session should be cleaned up
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            session = loop.run_until_complete(manager.get_session(UUID(session_id)))
            assert session is None
        finally:
            loop.close()

    def test_end_session_flow(
        self, test_client: TestClient, _setup_handler_deps
    ) -> None:
        manager, dispatcher = _setup_handler_deps
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
            ws.receive_json()  # ack

            ws.send_json({
                "type": "end_session",
                "payload": {},
            })

    def test_receive_binary_frame(
        self,
        test_client: TestClient,
        _setup_handler_deps,
        audio_frame_bytes: bytes,
    ) -> None:
        manager, dispatcher = _setup_handler_deps
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
            ws.receive_json()  # ack

            ws.send_bytes(audio_frame_bytes)
