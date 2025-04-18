#!/usr/bin/env python
"""Script to clear out Mem0 and Graphiti data.

This utility script helps with clearing data during testing and development.
WARNING: This script deletes data permanently. Use with caution.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.memory import MemoryService
from app.services.graph import GraphitiService

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
    
    # Clear both if neither is specifically requested
    if not args.mem0 and not args.graphiti:
        if args.all:
            results["mem0"] = await clear_mem0(all_users=True)
            results["graphiti"] = await clear_graphiti(all_users=True)
        elif args.user_id:
            results["mem0"] = await clear_mem0(user_id=args.user_id)
            results["graphiti"] = await clear_graphiti(user_id=args.user_id, scope=args.scope)
        else:
            logger.error("❌ Either --all or --user-id must be specified")
            return
    
    logger.info("-" * 60)
    logger.info("Data clearing operations completed")
    logger.info("-" * 60)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear data from Mem0 and Graphiti")
    
    # Options for what to clear
    parser.add_argument("--mem0", action="store_true", help="Clear Mem0 data only")
    parser.add_argument("--graphiti", action="store_true", help="Clear Graphiti data only")
    
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