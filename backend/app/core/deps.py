from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=5)
_async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


async def get_current_user() -> str:
    return DEV_USER_ID
