#!/usr/bin/env python
"""Script to ingest all files in the data directory.

This script can be run directly to process all files in the data directory.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.ingestion import IngestionService
from app.worker.tasks import process_directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Ingest files from the data directory")
    parser.add_argument(
        "--user-id", 
        type=str, 
        default="system",
        help="User ID to associate with ingested content"
    )
    parser.add_argument(
        "--subdirectory", 
        type=str, 
        default=None,
        help="Optional subdirectory to process (relative to data dir)"
    )
    parser.add_argument(
        "--async", 
        action="store_true",
        dest="use_async",
        help="Run in async mode (directly without Celery)"
    )
    return parser.parse_args()


async def run_async_ingestion(directory, user_id):
    """Run ingestion directly in async mode."""
    logger.info(f"Starting async ingestion of directory: {directory or 'data'}")
    ingestion_service = IngestionService()
    result = await ingestion_service.process_directory(directory, user_id)
    logger.info(f"Ingestion completed with {result['successful']} successes and {result['failed']} failures")
    logger.info(f"Skipped {result['skipped']} files")
    return result


def run_celery_ingestion(directory, user_id):
    """Run ingestion using Celery task."""
    logger.info(f"Queuing Celery task to ingest directory: {directory or 'data'}")
    task = process_directory.delay(directory, user_id)
    logger.info(f"Task queued with ID: {task.id}")
    logger.info("The task will run asynchronously in the Celery worker.")
    logger.info("Check Celery logs for progress and results.")
    return {"task_id": task.id}


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.use_async:
        # Run directly in async mode
        result = asyncio.run(run_async_ingestion(args.subdirectory, args.user_id))
        logger.info(f"Async ingestion completed: {result}")
    else:
        # Use Celery task
        result = run_celery_ingestion(args.subdirectory, args.user_id)
        logger.info(f"Celery task queued: {result}")


if __name__ == "__main__":
    main() 