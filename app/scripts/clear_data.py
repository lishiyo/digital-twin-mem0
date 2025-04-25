#!/usr/bin/env python
"""Script to clear out Mem0, Graphiti data, and PostgreSQL tables.

This utility script helps with clearing data during testing and development.
WARNING: This script deletes data permanently. Use with caution.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import anext for Python 3.10+ compatibility
# For Python 3.9 and below, use a helper function instead
try:
    from builtins import anext  # Python 3.10+
except ImportError:
    # Fallback for Python 3.9 and below
    async def anext(ait):
        return await ait.__anext__()

from app.services.memory import MemoryService
from app.services.graph import GraphitiService
from app.api.deps import get_db
from app.db.models.chat_message import ChatMessage
from app.db.models.conversation import Conversation
from app.db.models.ingested_document import IngestedDocument
from app.db.models.message_feedback import MessageFeedback
from app.db.models.user_profile import UserProfile
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def clear_mem0(user_id=None, all_users=False):
    """Clear data from Mem0.
    
    Args:
        user_id: Specific user ID to clear data for
        all_users: Whether to clear data for all users
        
    Returns:
        Dict with results
    """
    memory_service = MemoryService()
    
    if all_users:
        logger.warning("⚠️ Clearing ALL data from Mem0...")
        result = await memory_service.clear_all()
        logger.info("✅ Mem0 data cleared for all users")
        return result
    elif user_id:
        logger.warning(f"⚠️ Clearing Mem0 data for user: {user_id}")
        result = await memory_service.clear_for_user(user_id)
        logger.info(f"✅ Mem0 data cleared for user: {user_id}")
        return result
    else:
        logger.error("❌ No user_id provided and all_users=False. Nothing to clear.")
        return {"error": "No user_id provided and all_users=False"}


async def clear_graphiti(user_id=None, all_users=False, scope=None):
    """Clear data from Graphiti.
    
    Args:
        user_id: Specific user ID to clear data for
        all_users: Whether to clear data for all users
        scope: Content scope to clear ("user", "twin", "global")
        
    Returns:
        Dict with results
    """
    graphiti_service = GraphitiService()
    
    if all_users:
        logger.warning("⚠️ Clearing ALL data from Graphiti...")
        result = await graphiti_service.clear_all()
        logger.info("✅ Graphiti data cleared for all users")
        return result
    elif user_id:
        if scope:
            logger.warning(f"⚠️ Clearing Graphiti data for user: {user_id}, scope: {scope}")
            result = await graphiti_service.clear_for_user(user_id, scope=scope)
            logger.info(f"✅ Graphiti data cleared for user: {user_id}, scope: {scope}")
        else:
            logger.warning(f"⚠️ Clearing Graphiti data for user: {user_id}, all scopes")
            result = await graphiti_service.clear_for_user(user_id)
            logger.info(f"✅ Graphiti data cleared for user: {user_id}")
        return result
    else:
        logger.error("❌ No user_id provided and all_users=False. Nothing to clear.")
        return {"error": "No user_id provided and all_users=False"}


async def clear_postgres_tables(user_id=None, all_users=False):
    """Clear data from PostgreSQL tables.
    
    Args:
        user_id: Specific user ID to clear data for
        all_users: Whether to clear data for all users
        
    Returns:
        Dict with results
    """
    results = {}
    
    # Use the database session within an async with block to properly manage its lifecycle
    async for db in get_db():
        try:
            # Clear ChatMessage table
            if all_users:
                logger.warning("⚠️ Clearing ALL chat messages from PostgreSQL...")
                stmt = delete(ChatMessage)
                await db.execute(stmt)
                results["chat_messages"] = "All chat messages deleted"
            elif user_id:
                logger.warning(f"⚠️ Clearing chat messages for user: {user_id}")
                stmt = delete(ChatMessage).where(ChatMessage.user_id == user_id)
                result = await db.execute(stmt)
                results["chat_messages"] = f"Deleted {result.rowcount} chat messages for user {user_id}"
            
            # Clear Conversation table
            if all_users:
                logger.warning("⚠️ Clearing ALL conversations from PostgreSQL...")
                stmt = delete(Conversation)
                await db.execute(stmt)
                results["conversations"] = "All conversations deleted"
            elif user_id:
                logger.warning(f"⚠️ Clearing conversations for user: {user_id}")
                stmt = delete(Conversation).where(Conversation.user_id == user_id)
                result = await db.execute(stmt)
                results["conversations"] = f"Deleted {result.rowcount} conversations for user {user_id}"
            
            # Clear IngestedDocument table
            if all_users:
                logger.warning("⚠️ Clearing ALL ingested documents from PostgreSQL...")
                stmt = delete(IngestedDocument)
                await db.execute(stmt)
                results["ingested_documents"] = "All ingested documents deleted"
            elif user_id:
                logger.warning(f"⚠️ Clearing ingested documents for user: {user_id}")
                stmt = delete(IngestedDocument).where(IngestedDocument.user_id == user_id)
                result = await db.execute(stmt)
                results["ingested_documents"] = f"Deleted {result.rowcount} ingested documents for user {user_id}"
            
            # Clear MessageFeedback table
            if all_users:
                logger.warning("⚠️ Clearing ALL message feedback from PostgreSQL...")
                stmt = delete(MessageFeedback)
                await db.execute(stmt)
                results["message_feedback"] = "All message feedback deleted"
            elif user_id:
                logger.warning(f"⚠️ Clearing message feedback for user: {user_id}")
                stmt = delete(MessageFeedback).where(MessageFeedback.user_id == user_id)
                result = await db.execute(stmt)
                results["message_feedback"] = f"Deleted {result.rowcount} message feedback for user {user_id}"
            
            # Reset UserProfile fields (don't delete the profile itself)
            if all_users:
                logger.warning("⚠️ Resetting ALL user profiles in PostgreSQL...")
                stmt = update(UserProfile).values(
                    preferences={},
                    interests=[],
                    skills=[],
                    dislikes=[],
                    attributes=[],
                    communication_style={},
                    key_relationships=[]
                )
                await db.execute(stmt)
                results["user_profiles"] = "All user profiles reset"
            elif user_id:
                logger.warning(f"⚠️ Resetting user profile for user: {user_id}")
                stmt = update(UserProfile).where(UserProfile.user_id == user_id).values(
                    preferences={},
                    interests=[],
                    skills=[],
                    dislikes=[],
                    attributes=[],
                    communication_style={},
                    key_relationships=[]
                )
                result = await db.execute(stmt)
                results["user_profiles"] = f"Reset profile for user {user_id}"
            
            # Commit the changes
            await db.commit()
            logger.info("✅ PostgreSQL tables cleared successfully")
            
        except Exception as e:
            await db.rollback()
            error_msg = f"❌ Error clearing PostgreSQL tables: {str(e)}"
            logger.error(error_msg)
            results["error"] = error_msg
        
        # No need to manually close the session - it's handled by the async with block
        # Breaking out of the loop after processing the first session
        break
    
    return results


def confirm_action():
    """Ask for user confirmation before proceeding with destructive action."""
    response = input("⚠️ This will permanently delete data. Are you sure? (y/N): ")
    return response.lower() in ["y", "yes"]


async def main(args):
    """Run the data clearing operations."""
    # Check confirmation for operations that affect all users
    if args.all and not args.force and not confirm_action():
        logger.info("Operation canceled by user.")
        return
    
    results = {}
    
    # Clear Mem0 if requested
    if args.mem0:
        if args.all:
            results["mem0"] = await clear_mem0(all_users=True)
        elif args.user_id:
            results["mem0"] = await clear_mem0(user_id=args.user_id)
        else:
            logger.error("❌ Either --all or --user-id must be specified")
            return
    
    # Clear Graphiti if requested
    if args.graphiti:
        if args.all:
            results["graphiti"] = await clear_graphiti(all_users=True)
        elif args.user_id:
            results["graphiti"] = await clear_graphiti(user_id=args.user_id, scope=args.scope)
        else:
            logger.error("❌ Either --all or --user-id must be specified")
            return
    
    # Clear PostgreSQL if requested
    if args.postgres:
        if args.all:
            results["postgres"] = await clear_postgres_tables(all_users=True)
        elif args.user_id:
            results["postgres"] = await clear_postgres_tables(user_id=args.user_id)
        else:
            logger.error("❌ Either --all or --user-id must be specified")
            return
    
    # Clear all services if none is specifically requested
    if not args.mem0 and not args.graphiti and not args.postgres:
        if args.all:
            results["mem0"] = await clear_mem0(all_users=True)
            results["graphiti"] = await clear_graphiti(all_users=True)
            results["postgres"] = await clear_postgres_tables(all_users=True)
        elif args.user_id:
            results["mem0"] = await clear_mem0(user_id=args.user_id)
            results["graphiti"] = await clear_graphiti(user_id=args.user_id, scope=args.scope)
            results["postgres"] = await clear_postgres_tables(user_id=args.user_id)
        else:
            logger.error("❌ Either --all or --user-id must be specified")
            return
    
    logger.info("-" * 60)
    logger.info("Data clearing operations completed")
    logger.info("-" * 60)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear data from Mem0, Graphiti, and PostgreSQL")
    
    # Options for what to clear
    parser.add_argument("--mem0", action="store_true", help="Clear Mem0 data only")
    parser.add_argument("--graphiti", action="store_true", help="Clear Graphiti data only")
    parser.add_argument("--postgres", action="store_true", help="Clear PostgreSQL data only")
    
    # Options for who to clear
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Clear data for all users")
    group.add_argument("--user-id", type=str, help="Clear data for a specific user ID")
    
    # Additional options
    parser.add_argument("--scope", type=str, choices=["user", "twin", "global"], 
                        help="Content scope to clear (Graphiti only)")
    parser.add_argument("--force", action="store_true", 
                        help="Skip confirmation prompt (use with caution)")
    
    args = parser.parse_args()
    
    asyncio.run(main(args)) 