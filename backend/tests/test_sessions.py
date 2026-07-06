"""Tests for the sessions API endpoints."""

import pytest
from httpx import AsyncClient


class TestListSessions:
    """GET /api/v1/sessions"""

    async def test_list_requires_auth(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/sessions")
        assert resp.status_code == 401

    async def test_list_returns_empty(self, async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        resp = await async_client.get("/api/v1/sessions", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["sessions"] == []
        assert body["total"] == 0

    async def test_list_returns_empty_with_valid_token(self, async_client: AsyncClient) -> None:
        """Same as above but using a freshly created token to confirm flow."""
        from app.core.security import create_access_token

        token = create_access_token(user_id="any-user")
        headers = {"Authorization": f"Bearer {token}"}
        resp = await async_client.get("/api/v1/sessions", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []
