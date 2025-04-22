"""Test fixtures for the application."""

import asyncio
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.services.graph import GraphitiService
from app.services.memory import MemoryService


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Create a new database session for each test."""
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def graphiti_service():
    """Return a GraphitiService instance."""
    return GraphitiService()


@pytest.fixture
def memory_service():
    """Return a MemoryService instance."""
    return MemoryService()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user_id = "test-user-id"
    result = await db_session.execute(
        insert(User).values(
            id=user_id,
            handle="testuser",
            email="test@example.com",
            is_active=True,
            is_admin=False,
        ).returning(User)
    )
    user = result.scalar_one()
    await db_session.commit()
    return user 