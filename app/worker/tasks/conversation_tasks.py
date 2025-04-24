import logging
from typing import Dict, Optional, Any, List

from app.worker.celery_app import celery_app
from app.db.session import get_db_session  # Use synchronous session
from app.services.conversation.mem0_ingestion_sync import SyncChatMem0Ingestion
from sqlalchemy import select
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.conversation_tasks.process_chat_message")
def process_chat_message(message_id: str) -> Dict[str, Any]:
    """Process a single chat message for Mem0 ingestion.
    
    Args:
        message_id: ID of the message to process
        
    Returns:
        Processing results dictionary
    """
    try:
        # Use fully synchronous implementation
        mem0_result = _process_message_sync(message_id)
        
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

            logger.info(f"Processing message: {message}")
            
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
    # Use a synchronous DB session
    with get_db_session() as db:
        try:
            # Get conversation
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "conversation_id": conversation_id
                }
            
            # Import here to avoid circular imports
            from app.services.conversation.summarization import ConversationSummarizationService
            import asyncio
            
            # Define the async function that will be run
            async def run_summarization():
                # Get memory service
                from app.services.memory import MemoryService
                from app.db.session import get_async_session
                
                # Create a new async session
                async with get_async_session() as async_db:
                    memory_service = MemoryService()
                    summarization_service = ConversationSummarizationService(async_db, memory_service)
                    return await summarization_service.generate_summary(conversation_id)
            
            # Create a brand new event loop
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            try:
                # Use the new loop to run the coroutine to completion
                result = new_loop.run_until_complete(run_summarization())
                return result
            finally:
                # Always clean up the loop to prevent resource leaks
                new_loop.close()
            
        except Exception as e:
            logger.error(f"Error in _summarize_conversation_sync: {str(e)}")
            raise
