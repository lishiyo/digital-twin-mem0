"""Worker tasks for Graphiti ingestion."""

import logging
from typing import Dict, Optional, Any, List
import asyncio

from app.worker.celery_app import celery_app
from app.db.session import get_db_session
from app.services.conversation.graphiti_ingestion import ChatGraphitiIngestion
from app.services.graph import GraphitiService
from app.services.ingestion.entity_extraction_factory import get_entity_extractor
from sqlalchemy import select
from app.db.models.chat_message import ChatMessage
from app.db.models.conversation import Conversation
from app.services.traits.service import TraitExtractionService
from app.services.extraction_pipeline import ExtractionPipeline

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
            # Get the message (sync query okay)
            # Important: Fetch the message here, *not* just check for processed status,
            # as the ingestion service needs the message object.
            query = select(ChatMessage).where(ChatMessage.id == message_id)
            result = db.execute(query)
            message = result.scalars().first()
            
            if not message:
                logger.warning(f"GRAPHITI_TASK: Message {message_id} not found when task started.")
                return {
                    "status": "error",
                    "reason": "message_not_found_in_task",
                    "message_id": message_id
                }

            # Check processed status *after* fetching, before doing heavy work
            if message.processed_in_graphiti:
                 logger.info(f"GRAPHITI_TASK: Message {message_id} already processed, skipping.")
                 return {
                     "status": "skipped",
                     "reason": "already_processed",
                     "message_id": message_id
                 }
            
            # Create services needed by ChatGraphitiIngestion
            graphiti_service = GraphitiService()
            entity_extractor = get_entity_extractor()
            
            # Create the ingestion service
            ingestion_service = ChatGraphitiIngestion(db, graphiti_service, entity_extractor)
            
            # Call the service method which now handles async execution internally
            logger.info(f"GRAPHITI_TASK: Calling ChatGraphitiIngestion.process_message for {message_id}")
            process_result = ingestion_service.process_message(message)
            logger.info(f"GRAPHITI_TASK: ChatGraphitiIngestion.process_message completed for {message_id} with status {process_result.get('status')}")
            return process_result
            
        except Exception as e:
            logger.error(f"GRAPHITI_TASK: Unhandled error processing message {message_id}: {str(e)}", exc_info=True)
            # Return error status
            return {
                "status": "error",
                "reason": f"Unhandled exception in task: {str(e)}",
                "message_id": message_id
            }


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