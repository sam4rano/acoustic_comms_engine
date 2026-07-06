"""Tests for the Session SQLAlchemy model."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import Session
from app.models.user import User


class TestCreateSession:
    """Creating a Session linked to a User."""

    async def _create_user(self, db: AsyncSession, email: str) -> User:
        user = User(email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def test_create_session(self, test_db: AsyncSession) -> None:
        user = await self._create_user(test_db, "session-test@example.com")

        session = Session(user_id=user.id, language="fr")
        test_db.add(session)
        await test_db.commit()
        await test_db.refresh(session)

        assert session.id is not None
        assert isinstance(session.id, uuid.UUID)
        assert session.user_id == user.id
        assert session.language == "fr"
        assert session.config == {}

    async def test_session_belongs_to_user(self, test_db: AsyncSession) -> None:
        user = await self._create_user(test_db, "rel-test@example.com")

        session = Session(user_id=user.id)
        test_db.add(session)
        await test_db.commit()
        await test_db.refresh(session)

        assert session.user.id == user.id
        assert session.user.email == "rel-test@example.com"

    async def test_user_has_sessions_collection(self, test_db: AsyncSession) -> None:
        user = await self._create_user(test_db, "collection-test@example.com")

        s1 = Session(user_id=user.id)
        s2 = Session(user_id=user.id)
        test_db.add_all([s1, s2])
        await test_db.commit()

        # Eager-load the relationship to avoid the async lazy-load issue
        result = await test_db.execute(
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.sessions))
        )
        user = result.scalar_one()

        assert len(user.sessions) == 2


class TestSessionDefaults:
    """Default values are stored on INSERT — check after commit+refresh."""

    async def test_session_status_default(self, test_db: AsyncSession) -> None:
        user = User(email="defaults@example.com")
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        session = Session(user_id=user.id)
        test_db.add(session)
        await test_db.commit()
        await test_db.refresh(session)

        assert session.status == "created"

    async def test_session_language_default(self, test_db: AsyncSession) -> None:
        user = User(email="lang-test@example.com")
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        session = Session(user_id=user.id)
        test_db.add(session)
        await test_db.commit()
        await test_db.refresh(session)

        assert session.language == "en"

    async def test_session_config_defaults_to_empty_dict(
        self, test_db: AsyncSession
    ) -> None:
        user = User(email="config-test@example.com")
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        session = Session(user_id=user.id)
        test_db.add(session)
        await test_db.commit()
        await test_db.refresh(session)

        assert session.config == {}
