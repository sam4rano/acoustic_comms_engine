"""Tests for JWT token creation, decoding, and protected‑route guards."""

import jwt
import pytest
from httpx import AsyncClient

from datetime import timedelta

from app.core.config import settings
from app.core.security import create_access_token, decode_token


class TestTokenCreation:
    """Creating and decoding access tokens."""

    def test_access_token_creation(self) -> None:
        token = create_access_token(user_id="user-42")
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["sub"] == "user-42"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_access_token_payload_custom_sub(self) -> None:
        token = create_access_token(user_id="alice@example.com")
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["sub"] == "alice@example.com"


class TestExpiredToken:
    """Expired tokens are rejected at the decode level."""

    def test_expired_token_raises_on_decode(self) -> None:
        token = create_access_token(
            user_id="user-42",
            expires_delta=timedelta(hours=-1),
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )

    def test_decode_token_returns_empty_for_expired(self) -> None:
        token = create_access_token(
            user_id="user-42",
            expires_delta=timedelta(hours=-1),
        )
        payload = decode_token(token)
        assert payload == {}


class TestProtectedRoutes:
    """Requests that require a valid bearer token."""

    async def test_missing_authorization_header(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/sessions")
        assert resp.status_code == 401

    async def test_expired_token_rejected(self, async_client: AsyncClient, expired_auth_headers: dict[str, str]) -> None:
        resp = await async_client.get("/api/v1/sessions", headers=expired_auth_headers)
        assert resp.status_code == 401

    async def test_malformed_token_rejected(self, async_client: AsyncClient) -> None:
        headers = {"Authorization": "Bearer not-a-valid-jwt"}
        resp = await async_client.get("/api/v1/sessions", headers=headers)
        assert resp.status_code == 401
