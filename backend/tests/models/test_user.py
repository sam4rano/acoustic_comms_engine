"""Tests for the User SQLAlchemy model."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User


class TestCreateUser:
    """Creating and persisting a User record."""

    async def test_create_user(self, test_db: AsyncSession) -> None:
        user = User(email="alice@example.com", display_name="Alice")
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.email == "alice@example.com"
        assert user.display_name == "Alice"
        assert user.settings == {}
        assert user.created_at is not None

    async def test_create_user_minimal_fields(self, test_db: AsyncSession) -> None:
        """Only email is required; other fields use defaults."""
        user = User(email="bob@example.com")
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.email == "bob@example.com"
        assert user.display_name is None
        assert user.settings == {}

    async def test_user_custom_settings(self, test_db: AsyncSession) -> None:
        user = User(
            email="carol@example.com",
            settings={"theme": "dark", "notifications": False},
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.settings == {"theme": "dark", "notifications": False}


class TestEmailUniqueness:
    """The email column has a unique constraint."""

    async def test_email_unique_constraint(self, test_db: AsyncSession) -> None:
        user1 = User(email="dupe@example.com", display_name="First")
        test_db.add(user1)
        await test_db.commit()

        user2 = User(email="dupe@example.com", display_name="Second")
        test_db.add(user2)
        with pytest.raises(IntegrityError):
            await test_db.commit()
        await test_db.rollback()

    async def test_distinct_emails_allowed(self, test_db: AsyncSession) -> None:
        user_a = User(email="a@example.com")
        user_b = User(email="b@example.com")
        test_db.add_all([user_a, user_b])
        await test_db.commit()

        result = await test_db.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 2
