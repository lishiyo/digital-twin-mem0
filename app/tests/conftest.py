"""Test fixtures for the application."""

import pytest
import pytest_asyncio
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.core.config import settings
from app.db.models.user import User
from app.services.graph import GraphitiService
from app.services.memory import MemoryService


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a clean database session for a test."""
    # Create an engine connected to the test database
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create a sessionmaker
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create a session
    async with async_session() as session:
        yield session
        
        # Roll back any changes
        await session.rollback()
    
    # Drop all tables after the test is complete
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Dispose of the engine
    await engine.dispose()


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