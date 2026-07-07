import json
from typing import Annotated

from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "acoustic-comms-engine"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    # For Supabase, use the session pooler URL (port 6543)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/acoustic_comms"
    )

    # Supabase (optional — for Storage, Auth SDK usage)
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None

    # Cache / Queue
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Vector store
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: str | None = None

    # Object storage
    MINIO_ENDPOINT: str = Field(default="localhost:9000")
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_AUDIO: str = "audio-recordings"
    MINIO_BUCKET_EXPORTS: str = "analysis-exports"
    MINIO_USE_SSL: bool = False

    # Speech encoder
    SPEECH_ENCODER: str = "silero-vad"
    SPEECH_ENCODER_PATH: str = "models/speech_encoder.pt"

    # LLM
    LLM_BASE_URL: str = Field(default="http://localhost:11434/v1")
    LLM_MODEL: str = "qwen3-8b-instruct"
    LLM_FALLBACK_MODEL: str | None = None
    LLM_API_KEY: str = "not-needed"

    # Auth
    JWT_SECRET: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 30
    JWT_REFRESH_EXPIRATION_DAYS: int = 7

    # CORS
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return v
        return ["*"]

    # Analysis pipeline
    ANALYSIS_TIMEOUT_PER_AGENT_S: float = 120.0
    ANALYSIS_MIN_TURNS: int = 3
    ANALYSIS_TOP_K_TURNS: int = 15
    ANALYSIS_ACOUSTIC_NEIGHBORS: int = 5

    # Graph
    GRAPH_EDGE_TTL_HOURS: int = 24


settings = Settings()
