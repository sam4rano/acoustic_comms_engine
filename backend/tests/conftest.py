"""Test fixtures and configuration for the acoustic-comms-engine backend.

Environment variables are set before any app imports so pydantic-settings
picks them up. PostgreSQL-specific types (JSONB) are patched for SQLite
compatibility so tests can run without external services.
"""

import os
from collections.abc import AsyncGenerator
from datetime import timedelta
from pathlib import Path

# ── Environment (must happen before any app imports) ─────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

# ── PostgreSQL → SQLite compatibility ────────────────────────────────────────
# The models use postgresql.JSONB which aiosqlite doesn't recognise.
# Monkey-patch it to sqlalchemy.JSON before any model imports.
import sqlalchemy
from sqlalchemy.dialects import postgresql as _pg

_pg.JSONB = sqlalchemy.JSON

# ── Patch engine-creation kwargs ──────────────────────────────────────────────
# ``app.core.deps`` and ``app.database`` create sync-pooled engines at import
# time with PostgreSQL-specific kwargs (pool_size, pool_pre_ping) that the
# SQLite dialect rejects.  Strip them before those modules load.
import sqlalchemy.ext.asyncio as _sa_async

_original_create_engine = _sa_async.create_async_engine


def _patched_create_engine(url, **kwargs):
    kwargs.pop("pool_size", None)
    kwargs.pop("max_overflow", None)
    kwargs.pop("pool_pre_ping", None)
    kwargs.pop("pool_recycle", None)
    return _original_create_engine(url, **kwargs)


_sa_async.create_async_engine = _patched_create_engine

# ── App imports (safe after env / patch) ─────────────────────────────────────
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.main import app
from app.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session.

    pytest-asyncio >= 0.24 no longer provides this fixture automatically;
    defining it here with session scope avoids re-creating the loop for
    every single test function.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db():
    """Remove SQLite test database after the session ends."""
    yield
    db_path = Path("test.db")
    if db_path.exists():
        db_path.unlink()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create tables, yield a clean session, drop tables.

    Each test function gets a fresh database — no cross-test leakage.
    Because SQLite does not support nested transactions, we create and
    drop the full schema per test.  This is fast enough for the current
    test count; if the suite grows, switch to a shared engine with
    transactional rollback.
    """
    engine = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(
    test_db: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async client wired to the FastAPI app.

    The ``get_db`` dependency is overridden with the test session so
    every request hits the temporary in-memory / file database.
    """

    async def _override_db():
        yield test_db

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Bearer-authorization header with a valid access token."""
    token = create_access_token(user_id="test-user-id")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def expired_auth_headers() -> dict[str, str]:
    """Bearer-authorization header with an already-expired token."""
    token = create_access_token(
        user_id="test-user-id",
        expires_delta=timedelta(hours=-1),
    )
    return {"Authorization": f"Bearer {token}"}
