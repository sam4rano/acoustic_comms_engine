import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def startup() -> None:
    logger.info(
        "Starting %s v%s",
        settings.APP_NAME,
        settings.VERSION,
    )
    logger.info("Database:     %s", _mask_url(settings.DATABASE_URL))
    logger.info("Redis:        %s", settings.REDIS_URL)
    logger.info("Qdrant:       %s", settings.QDRANT_URL)
    logger.info("LLM endpoint: %s", settings.LLM_BASE_URL)
    logger.info("Log level:    %s", settings.LOG_LEVEL)


async def shutdown() -> None:
    logger.info("Shutting down — closing connections")


def _mask_url(url: str) -> str:
    """Mask credentials in a connection URL for safe logging."""
    if "@" in url:
        scheme_part, _, rest = url.partition("://")
        creds, _, host = rest.partition("@")
        return f"{scheme_part}://***:***@{host}"
    return url
