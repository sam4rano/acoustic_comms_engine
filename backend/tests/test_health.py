"""Tests for the health-check endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.main import app


class TestHealth:
    """GET /health — basic liveness probe."""

    async def test_health_returns_ok(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    async def test_health_includes_version(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        assert "version" in resp.json()


class TestReadiness:
    """GET /health/ready — dependency check (database)."""

    async def test_ready_with_db(self, async_client: AsyncClient) -> None:
        """When the database is reachable the endpoint reports 'ok'."""
        resp = await async_client.get("/health/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"

    async def test_ready_without_db(self, async_client: AsyncClient) -> None:
        """When the database is unreachable the endpoint reports 'degraded'."""
        async def _broken_db():
            session = AsyncMock(spec=AsyncSession)
            session.execute.side_effect = Exception("connection refused")
            yield session

        app.dependency_overrides[get_db] = _broken_db
        try:
            resp = await async_client.get("/health/ready")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "degraded"
            assert body["database"] == "unreachable"
        finally:
            app.dependency_overrides.pop(get_db, None)
