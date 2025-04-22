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
        return _process_message_sync(message_id)
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
        return _process_pending_messages_sync(limit)
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
        return _process_conversation_sync(conversation_id)
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
            
            # This will be implemented as part of Task 3.1.4
            logger.info(f"Would summarize conversation {conversation_id}")
            
            return {
                "status": "not_implemented",
                "conversation_id": conversation_id,
                "message": "Conversation summarization will be implemented in Task 3.1.4"
            }
            
        except Exception as e:
            logger.error(f"Error in _summarize_conversation_sync: {str(e)}")
            raise
