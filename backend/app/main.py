from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analysis, health, sessions
from app.core.config import settings
from app.core.events import shutdown, startup
from app.streaming import router as streaming_router
from app.streaming.manager import StreamSessionManager
from app.streaming.dispatcher import StreamDispatcher
from app.streaming.router import setup_streaming
from app.audio.pipeline import AudioPipeline
from app.speech.encoder import SpeechEncoder
from app.speech.registry import HeadRegistry
from app.speech.service import SpeechService


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    _init_streaming()
    yield
    await shutdown()


def _init_streaming() -> None:
    """Wire up streaming dependencies lazily (encoder/heads may not be loaded)."""
    try:
        audio_pipeline = AudioPipeline()
        encoder = SpeechEncoder(device="cpu")
        registry = HeadRegistry()
        speech_service = SpeechService(encoder=encoder, registry=registry)
        manager = StreamSessionManager()
        dispatcher = StreamDispatcher(audio_pipeline, speech_service, manager)
        setup_streaming(manager, dispatcher)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Streaming layer not fully initialized — encoder model may not be loaded yet"
        )


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
app.include_router(streaming_router)


@app.get("/health")
async def root_health() -> dict:
    return {"status": "ok", "version": settings.VERSION}
