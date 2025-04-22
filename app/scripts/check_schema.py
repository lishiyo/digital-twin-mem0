#!/usr/bin/env python
"""Script to check database schema for debugging."""

import asyncio
import logging
from sqlalchemy import text

from app.db.session import get_async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_schema():
    """Check the database schema for the chat_message table."""
    async with get_async_session() as db:
        # Execute SQL directly to verify
        result = await db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'chat_message'"))
        sql_columns = [row[0] for row in result]
        logger.info(f"All columns in chat_message table: {sorted(sql_columns)}")
        
        # Check for mem0 specific fields
        mem0_columns = [col for col in sql_columns if 'mem0' in col]
        logger.info(f"Mem0-related columns: {mem0_columns}")


if __name__ == "__main__":
    asyncio.run(check_schema()) 