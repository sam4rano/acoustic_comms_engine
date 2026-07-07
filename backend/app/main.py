import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analysis, health, sessions
from app.core.config import settings
from app.core.events import shutdown, startup

logger = logging.getLogger(__name__)

_streaming_available = False
try:
    from app.streaming import router as streaming_router
    from app.streaming.manager import StreamSessionManager
    from app.streaming.dispatcher import StreamDispatcher
    from app.streaming.router import setup_streaming
    from app.audio.pipeline import AudioPipeline
    from app.speech.encoder import SpeechEncoder
    from app.speech.registry import HeadRegistry
    from app.speech.service import SpeechService
    _streaming_available = True
except ImportError:
    logger.info("Streaming layer unavailable (torch not installed — HTTP-only mode)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    if _streaming_available:
        await _init_streaming()
    yield
    await shutdown()


async def _init_streaming() -> None:
    try:
        encoder = SpeechEncoder(device="cpu")
        audio_pipeline = AudioPipeline()
        registry = HeadRegistry()
        speech_service = SpeechService(encoder=encoder, registry=registry)

        redis = None
        try:
            from urllib.parse import urlparse
            from app.memory.backends.redis_cache import RedisCache
            parsed = urlparse(settings.REDIS_URL)
            redis = RedisCache(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                db=int((parsed.path or "/0").lstrip("/") or 0),
            )
        except Exception:
            logger.debug("Redis not available for stream sessions")

        manager = StreamSessionManager(redis=redis)
        dispatcher = StreamDispatcher(audio_pipeline, speech_service, manager)
        setup_streaming(manager, dispatcher)
    except Exception as exc:
        logger.warning("Streaming layer not fully initialized: %s", exc)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
if _streaming_available:
    app.include_router(streaming_router)


@app.get("/health")
async def root_health() -> dict:
    return {"status": "ok", "version": settings.VERSION}
