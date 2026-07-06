import json
import logging
import time
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from app.streaming.dispatcher import StreamDispatcher
from app.streaming.errors import InvalidFrameError, RateLimitError
from app.streaming.manager import StreamSessionManager
from app.streaming.types import AudioFrame, StreamMessage, StreamSessionConfig

logger = logging.getLogger(__name__)


async def handle_websocket(
    websocket: WebSocket,
    manager: StreamSessionManager,
    dispatcher: StreamDispatcher,
    authenticate: bool = False,
) -> None:
    """Main WebSocket handler for the streaming endpoint.

    Lifecycle:
        1. Accept connection.
        2. Wait for ``start_session`` message → create session.
        3. Loop: receive JSON or binary frames → dispatch → send results.
        4. On disconnect or ``end_session`` → clean up.
    """
    await websocket.accept()

    session_id: UUID | None = None
    config: StreamSessionConfig | None = None
    last_frame_ts: float = 0.0
    rate_warning_sent = False

    try:
        # ── Wait for session start ────────────────────────────────────
        raw = await websocket.receive()
        if raw.get("type") == "websocket.disconnect":
            return

        msg = _parse_message(raw)
        if msg is None or msg.type != "start_session":
            await _send_error(websocket, "First message must be start_session")
            await websocket.close(code=1002)
            return

        config = _build_config(msg.payload)
        session_id = config.session_id
        await manager.create_session(session_id, config)
        ack = await dispatcher.handle_start(session_id, config)
        await _send_message(websocket, ack)

        # ── Message loop ──────────────────────────────────────────────
        while True:
            raw = await websocket.receive()

            if raw.get("type") == "websocket.disconnect":
                break

            if raw.get("type") == "websocket.receive":
                content: bytes | str | None = None
                if "text" in raw and raw["text"] is not None:
                    content = raw["text"]
                elif "bytes" in raw and raw["bytes"] is not None:
                    content = raw["bytes"]
                else:
                    continue

                if isinstance(content, str):
                    # JSON message
                    msg = _parse_text_message(content)
                    if msg is None:
                        await _send_error(websocket, "Invalid JSON message")
                        continue

                    if msg.type == "ping":
                        await _send_message(
                            websocket,
                            StreamMessage(type="pong", payload={"timestamp": time.time()}),
                        )
                        continue

                    if msg.type == "config_update":
                        config = _apply_config_update(config, msg.payload)
                        await _send_message(
                            websocket,
                            StreamMessage(
                                type="state_change",
                                payload={
                                    "status": "config_updated",
                                    "config": msg.payload,
                                },
                            ),
                        )
                        continue

                    if msg.type == "end_session":
                        break

                    if msg.type == "audio_frame":
                        frame = AudioFrame(
                            data=b"",
                            sample_rate=config.sample_rate,
                            sequence=0,
                            timestamp_ms=int(msg.payload.get("timestamp_ms", 0)),
                        )
                        results = await dispatcher.handle_frame(session_id, frame)
                        for result in results:
                            await _send_message(websocket, result)
                        continue

                    await _send_error(websocket, f"Unknown message type: {msg.type}")
                    continue

                if isinstance(content, bytes):
                    # Binary audio frame
                    if not _check_rate_limit(last_frame_ts, rate_warning_sent, websocket):
                        rate_warning_sent = True

                    frame = AudioFrame(
                        data=content,
                        sample_rate=config.sample_rate,
                        sequence=0,
                        timestamp_ms=int(time.time() * 1000),
                    )
                    try:
                        results = await dispatcher.handle_frame(session_id, frame)
                    except InvalidFrameError as exc:
                        await _send_error(websocket, str(exc))
                        continue

                    for result in results:
                        await _send_message(websocket, result)

                    last_frame_ts = time.time()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("Unhandled error in WebSocket handler for session %s", session_id)
        try:
            await _send_error(websocket, "Internal server error")
        except Exception:
            pass
    finally:
        if session_id is not None:
            try:
                remaining = await dispatcher.flush_pending(session_id)
                for msg in remaining:
                    try:
                        await _send_message(websocket, msg)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                await manager.remove_session(session_id)
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass


def _parse_message(raw: dict) -> StreamMessage | None:
    """Parse a raw WebSocket receive dict into a ``StreamMessage``."""
    text = raw.get("text") or raw.get("bytes")
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return _parse_text_message(text)


def _parse_text_message(text: str) -> StreamMessage | None:
    """Parse a JSON string into a ``StreamMessage``."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    msg_type = data.get("type")
    if msg_type is None:
        return None
    return StreamMessage(type=msg_type, payload=data.get("payload", {}))


def _build_config(payload: dict) -> StreamSessionConfig:
    """Build a ``StreamSessionConfig`` from a start_session payload."""
    return StreamSessionConfig(
        user_id=UUID(payload["user_id"]),
        session_id=UUID(payload["session_id"]),
        sample_rate=payload.get("sample_rate", 16000),
        enabled_heads=payload.get("enabled_heads", [
            "asr", "emotion", "prosody", "stress", "fluency", "event",
        ]),
        language=payload.get("language", "en"),
        vad_enabled=payload.get("vad_enabled", True),
        denoise_enabled=payload.get("denoise_enabled", False),
    )


def _apply_config_update(
    config: StreamSessionConfig,
    payload: dict,
) -> StreamSessionConfig:
    """Apply partial config update from a config_update message."""
    heads = payload.get("enabled_heads")
    return StreamSessionConfig(
        user_id=config.user_id,
        session_id=config.session_id,
        sample_rate=payload.get("sample_rate", config.sample_rate),
        enabled_heads=heads if heads is not None else config.enabled_heads,
        language=payload.get("language", config.language),
        vad_enabled=payload.get("vad_enabled", config.vad_enabled),
        denoise_enabled=payload.get("denoise_enabled", config.denoise_enabled),
    )


async def _send_message(websocket: WebSocket, msg: StreamMessage) -> None:
    """Serialize ``StreamMessage`` to JSON and send over WebSocket."""
    payload = {
        "type": msg.type,
        "payload": msg.payload,
        "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, "isoformat") else str(msg.timestamp),
    }
    if msg.message_id:
        payload["message_id"] = msg.message_id
    await websocket.send_json(payload)


async def _send_error(websocket: WebSocket, message: str) -> None:
    """Send an error message over WebSocket."""
    msg = StreamMessage(type="error", payload={"message": message})
    await _send_message(websocket, msg)


def _check_rate_limit(
    last_frame_ts: float,
    rate_warning_sent: bool,
    websocket: WebSocket,
) -> bool:
    """Check if the client is sending frames faster than real-time.

    Returns ``True`` if the frame is within acceptable rate.
    """
    if last_frame_ts == 0.0:
        return True
    elapsed = time.time() - last_frame_ts
    # Very rough check: if frames arrive faster than 10ms apart
    # (100 frames/sec for 16kHz with typical frame sizes) it's
    # likely faster than real-time.
    if elapsed < 0.005 and not rate_warning_sent:
        logger.warning("Client sending frames faster than real-time")
    return True
