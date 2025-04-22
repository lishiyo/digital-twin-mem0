#!/usr/bin/env python
"""Script to create a test user in the database."""

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.core.constants import DEFAULT_USER_ID, DEFAULT_USER_NAME
from app.db.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_test_user():
    """Create a test user if it doesn't already exist."""
    async with get_async_session() as db:
        # Check if user already exists
        query = select(User).where(User.id == DEFAULT_USER_ID)
        result = await db.execute(query)
        user = result.scalars().first()
        
        if user:
            logger.info(f"Test user '{DEFAULT_USER_ID}' already exists")
            return user
        
        # Create new test user
        logger.info(f"Creating test user '{DEFAULT_USER_ID}'")
        user = User(
            id=DEFAULT_USER_ID,
            handle=DEFAULT_USER_NAME,
            email="test@example.com",
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Created test user: {user.id}")
        return user


if __name__ == "__main__":
    asyncio.run(create_test_user()) 