"""Worker tasks for Graphiti ingestion."""

import logging
from typing import Dict, Optional, Any, List

from app.worker.celery_app import celery_app
from app.db.session import get_db_session
from app.services.conversation.graphiti_ingestion import ChatGraphitiIngestion
from app.services.graph import GraphitiService
from app.services.ingestion.entity_extraction_factory import get_entity_extractor
from sqlalchemy import select
from app.db.models.chat_message import ChatMessage
from app.db.models.conversation import Conversation

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.graphiti_tasks.process_chat_message_graphiti")
def process_chat_message_graphiti(message_id: str) -> Dict[str, Any]:
    """Process a single chat message for Graphiti ingestion.
    
    Args:
        message_id: ID of the message to process
        
    Returns:
        Processing results dictionary
    """
    try:
        # Use synchronous implementation
        return _process_message_graphiti_sync(message_id)
    except Exception as e:
        logger.error(f"Error processing message {message_id} for Graphiti: {str(e)}")
        return {
            "status": "error",
            "reason": str(e),
            "message_id": message_id
        }


@celery_app.task(name="app.worker.tasks.graphiti_tasks.process_pending_messages_graphiti")
def process_pending_messages_graphiti(limit: int = 50) -> Dict[str, Any]:
    """Process pending messages that haven't been ingested to Graphiti.
    
    Args:
        limit: Maximum number of messages to process
        
    Returns:
        Processing results dictionary
    """
    try:
        # Use synchronous implementation
        return _process_pending_messages_graphiti_sync(limit)
    except Exception as e:
        logger.error(f"Error processing pending messages for Graphiti: {str(e)}")
        return {
            "status": "error",
            "reason": str(e)
        }


@celery_app.task(name="app.worker.tasks.graphiti_tasks.process_conversation_graphiti")
def process_conversation_graphiti(conversation_id: str) -> Dict[str, Any]:
    """Process all messages in a conversation for Graphiti.
    
    Args:
        conversation_id: ID of the conversation to process
        
    Returns:
        Processing results dictionary
    """
    try:
        # Use synchronous implementation
        return _process_conversation_graphiti_sync(conversation_id)
    except Exception as e:
        logger.error(f"Error processing conversation {conversation_id} for Graphiti: {str(e)}")
        return {
            "status": "error",
            "reason": str(e),
            "conversation_id": conversation_id
        }


def _process_message_graphiti_sync(message_id: str) -> Dict[str, Any]:
    """Synchronous implementation of process_chat_message_graphiti."""
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
            
            # Create Graphiti service
            graphiti_service = GraphitiService()
            
            # Create entity extractor
            entity_extractor = get_entity_extractor()
            
            # Create ChatGraphitiIngestion service (now synchronous)
            ingestion_service = ChatGraphitiIngestion(db, graphiti_service, entity_extractor)
            
            # Process message synchronously
            return ingestion_service.process_message(message)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in _process_message_graphiti_sync: {str(e)}")
            raise


def _process_pending_messages_graphiti_sync(limit: int = 50) -> Dict[str, Any]:
    """Synchronous implementation of process_pending_messages_graphiti."""
    # Use a synchronous DB session
    with get_db_session() as db:
        try:
            # Create services
            graphiti_service = GraphitiService()
            entity_extractor = get_entity_extractor()
            ingestion_service = ChatGraphitiIngestion(db, graphiti_service, entity_extractor)
            
            # Process pending messages synchronously
            return ingestion_service.process_pending_messages(limit)
            
        except Exception as e:
            logger.error(f"Error in _process_pending_messages_graphiti_sync: {str(e)}")
            raise


def _process_conversation_graphiti_sync(conversation_id: str) -> Dict[str, Any]:
    """Synchronous implementation of process_conversation_graphiti."""
    # Use a synchronous DB session
    with get_db_session() as db:
        try:
            # Create services
            graphiti_service = GraphitiService()
            entity_extractor = get_entity_extractor()
            ingestion_service = ChatGraphitiIngestion(db, graphiti_service, entity_extractor)
            
            # Process conversation synchronously
            return ingestion_service.process_conversation(conversation_id)
            
        except Exception as e:
            logger.error(f"Error in _process_conversation_graphiti_sync: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "conversation_id": conversation_id
            } 