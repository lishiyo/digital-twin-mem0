import logging
from typing import Dict, Optional, Any, List

from app.worker.celery_app import celery_app
from app.db.session import get_db_session  # Use synchronous session
from app.services.conversation.mem0_ingestion_sync import SyncChatMem0Ingestion
from sqlalchemy import select
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
import asyncio

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.conversation_tasks.process_chat_message")
def process_chat_message(message_id: str) -> Dict[str, Any]:
    """Process a single chat message for Mem0 ingestion.
    
    Args:
        message_id: ID of the message to process
        
    Returns:
        Processing results dictionary
    """
    logger.info(f"TASK: Processing chat message {message_id}")
    try:
        # Use fully synchronous implementation
        mem0_result = _process_message_sync(message_id)
        logger.info(f"Processing message in mem0: {message_id} with result: {mem0_result}")
        
        # Trigger Graphiti processing asynchronously
        from app.worker.tasks.graphiti_tasks import process_chat_message_graphiti
        graphiti_task = process_chat_message_graphiti.delay(message_id)
        
        # Add Graphiti task ID to result
        mem0_result["graphiti_task_id"] = graphiti_task.id
        
        return mem0_result
        
    except Exception as e:
        logger.error(f"Error processing message {message_id}: {str(e)}")
        return {
            "status": "error",
            "reason": str(e),
            "message_id": message_id
        }


@celery_app.task(name="app.worker.tasks.conversation_tasks.process_pending_messages")
def process_pending_messages(limit: int = 50) -> Dict[str, Any]:
    """Process pending messages that haven't been ingested to Mem0.
    
    Args:
        limit: Maximum number of messages to process
        
    Returns:
        Processing results dictionary
    """
    try:
        # Use fully synchronous implementation
        mem0_result = _process_pending_messages_sync(limit)
        
        # Trigger Graphiti processing for pending messages
        from app.worker.tasks.graphiti_tasks import process_pending_messages_graphiti
        graphiti_task = process_pending_messages_graphiti.delay(limit)
        
        # Add Graphiti task ID to result
        mem0_result["graphiti_task_id"] = graphiti_task.id
        
        return mem0_result
        
    except Exception as e:
        logger.error(f"Error processing pending messages: {str(e)}")
        return {
            "status": "error",
            "reason": str(e)
        }


@celery_app.task(name="app.worker.tasks.conversation_tasks.process_conversation")
def process_conversation(conversation_id: str) -> Dict[str, Any]:
    """Process all messages in a conversation.
    
    Args:
        conversation_id: ID of the conversation to process
        
    Returns:
        Processing results dictionary
    """
    try:
        # Use fully synchronous implementation
        mem0_result = _process_conversation_sync(conversation_id)
        
        # Trigger Graphiti processing for the conversation
        from app.worker.tasks.graphiti_tasks import process_conversation_graphiti
        graphiti_task = process_conversation_graphiti.delay(conversation_id)
        
        # Add Graphiti task ID to result
        mem0_result["graphiti_task_id"] = graphiti_task.id
        
        return mem0_result
        
    except Exception as e:
        logger.error(f"Error processing conversation {conversation_id}: {str(e)}")
        return {
            "status": "error",
            "reason": str(e),
            "conversation_id": conversation_id
        }


@celery_app.task(name="app.worker.tasks.conversation_tasks.check_and_queue_summarization")
def check_and_queue_summarization(conversation_id: str) -> Dict[str, Any]:
    """Checks if a conversation needs summarization and queues the task if needed."""
    logger.info(f"TASK: Checking summarization need for conversation {conversation_id}")
    
    # Use a synchronous path to avoid asyncio complexity in this checking task.
    # The actual summarization task will handle the async operations.
    with get_db_session() as db:
        try:
            # Perform a synchronous check to see if summarization is needed.
            
            # Get conversation (synchronous query)
            conv_query = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = db.execute(conv_query)
            conversation = conv_result.scalars().first()
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found during sync check.")
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "conversation_id": conversation_id
                }
            
            # Get count of unprocessed messages (synchronous query)
            # Use count() for efficiency instead of fetching all messages
            from sqlalchemy import func
            messages_query = (
                select(func.count(ChatMessage.id))
                .where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.processed_in_summary == False
                )
            )
            unprocessed_count = db.scalar(messages_query)
            
            logger.info(f"Synchronously found {unprocessed_count} unprocessed messages for conversation {conversation_id}")
            
            # Define threshold (consider moving to constants)
            MESSAGES_BEFORE_SUMMARY = 20 # Match value in ConversationSummarizationService
            should_summarize = unprocessed_count >= MESSAGES_BEFORE_SUMMARY
            
            if should_summarize:
                logger.info(f"TASK: Queuing summarization task for conversation {conversation_id}")
                # Queue the actual summarization task (which handles async internally)
                summary_task_result = summarize_conversation.delay(conversation_id)
                return {
                    "status": "queued",
                    "conversation_id": conversation_id,
                    "summary_task_id": summary_task_result.id
                }
            else:
                logger.info(f"TASK: Summarization not needed for conversation {conversation_id}")
                return {
                    "status": "not_needed",
                    "conversation_id": conversation_id
                }
                
        except Exception as e:
            logger.error(f"Error in synchronous check_and_queue_summarization: {str(e)}", exc_info=True)
            # Ensure db connection is released even on error
            # The 'with' statement handles rollback/commit implicitly on exception/success
            return {
                "status": "error",
                "reason": f"Sync check failed: {str(e)}",
                "conversation_id": conversation_id
            }


@celery_app.task(name="app.worker.tasks.conversation_tasks.summarize_conversation")
def summarize_conversation(conversation_id: str) -> Dict[str, Any]:
    """Generate a summary for a conversation.
    
    Args:
        conversation_id: ID of the conversation to summarize
        
    Returns:
        Summarization results dictionary
    """
    try:
        # Use fully synchronous implementation
        return _summarize_conversation_sync(conversation_id)
    except Exception as e:
        logger.error(f"Error summarizing conversation {conversation_id}: {str(e)}")
        return {
            "status": "error",
            "reason": str(e),
            "conversation_id": conversation_id
        }


def _process_message_sync(message_id: str) -> Dict[str, Any]:
    """Synchronous implementation of process_chat_message."""
    # Use a synchronous DB session
    with get_db_session() as db:
        try:
            # Get message
            query = select(ChatMessage).where(ChatMessage.id == message_id)
            result = db.execute(query)
            message = result.scalars().first()

            if not message:
                return {
                    "status": "error",
                    "reason": "message_not_found",
                    "message_id": message_id
                }
            
            # Create service with synchronous ingestion
            ingestion_service = SyncChatMem0Ingestion(db)
            
            # Process message
            result = ingestion_service.process_message(message)
            
            logger.info(f"Successfully processed message {message_id}")
            
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in _process_message_sync: {str(e)}")
            raise


def _process_pending_messages_sync(limit: int = 50) -> Dict[str, Any]:
    """Synchronous implementation of process_pending_messages."""
    # Use a synchronous DB session
    with get_db_session() as db:
        try:
            # Create service with synchronous ingestion
            ingestion_service = SyncChatMem0Ingestion(db)
            
            # Process pending messages
            result = ingestion_service.process_pending_messages(limit)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _process_pending_messages_sync: {str(e)}")
            raise


def _process_conversation_sync(conversation_id: str) -> Dict[str, Any]:
    """Synchronous implementation of process_conversation."""
    # Use a synchronous DB session
    with get_db_session() as db:
        try:
            # Create service with synchronous ingestion
            ingestion_service = SyncChatMem0Ingestion(db)
            
            # Process conversation
            result = ingestion_service.process_conversation(conversation_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _process_conversation_sync: {str(e)}")
            raise


def _summarize_conversation_sync(conversation_id: str) -> Dict[str, Any]:
    """Synchronous implementation of summarize_conversation."""
    # Use a synchronous DB session for initial verification
    with get_db_session() as db:
        try:
            # Get conversation synchronously first to avoid async complexity if not found
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "conversation_id": conversation_id
                }
            
            # Now that we know the conversation exists, proceed with the async part
            # Import here to avoid circular imports
            from app.services.conversation.summarization import ConversationSummarizationService
            from app.services.memory import MemoryService
            
            # Define the async function to perform the summarization
            async def run_summarization():
                # Import inside the async function
                from app.db.session import get_async_session
                
                # Create a fresh async session within the async context
                async with get_async_session() as async_db:
                    try:
                        memory_service = MemoryService()
                        summarization_service = ConversationSummarizationService(async_db, memory_service)
                        return await summarization_service.generate_summary(conversation_id)
                    except Exception as e:
                        logger.error(f"Error during async summarization call: {str(e)}", exc_info=True)
                        # Re-raise to be caught by the outer try/except
                        raise
            
            # Use asyncio.run() to execute the async function. 
            # This creates a new event loop and closes it automatically.
            try:
                result = asyncio.run(run_summarization())
                return result
            except Exception as e:
                # Catch errors specifically from the asyncio.run() call
                logger.error(f"Failed to summarize conversation {conversation_id} using asyncio.run: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "reason": f"Async execution failed: {str(e)}",
                    "conversation_id": conversation_id
                }

        except Exception as e:
            # Catch errors from the initial synchronous part or re-raised async errors
            logger.error(f"Error in _summarize_conversation_sync setup: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "conversation_id": conversation_id
            }
