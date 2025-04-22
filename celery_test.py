#!/usr/bin/env python3
"""Test script for Celery task registration."""

import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Run the test."""
    # Import the Celery app and tasks
    from app.worker.celery_app import celery_app
    import app.worker.tasks  # This should register the tasks
    import app.worker.tasks.conversation_tasks
    
    # List registered tasks
    logger.info("Registered Celery tasks:")
    for task_name in sorted(celery_app.tasks.keys()):
        logger.info(f"- {task_name}")
    
    # Check if our target task is registered
    target_task = "app.worker.tasks.conversation_tasks.process_chat_message"
    if target_task in celery_app.tasks:
        logger.info(f"✅ Task {target_task} is properly registered!")
    else:
        logger.error(f"❌ Task {target_task} is NOT registered!")
        return 1
    
    # Send a test task with a dummy ID
    logger.info("Sending test task...")
    test_result = celery_app.send_task(
        target_task,
        args=["test-message-id-123"],
        countdown=1
    )
    
    logger.info(f"Task scheduled with ID: {test_result.id}")
    logger.info("Check the worker logs to see if the task is processed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 