import logging
from typing import Dict, Optional, Any, List

from app.worker.celery_app import celery_app
from app.db.session import get_async_session
from app.services.conversation.mem0_ingestion import ChatMem0Ingestion
from app.services.memory import MemoryService
from sqlalchemy import select
from app.db.models.chat_message import ChatMessage
from app.db.models.conversation import Conversation
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# @celery_app.task(name="process_chat_message")
# def process_chat_message(message_id: str) -> Dict[str, Any]:
#     """NOT USED - Process a single chat message for Mem0 ingestion.
    
#     Args:
#         message_id: ID of the message to process
        
#     Returns:
#         Processing results dictionary
#     """
#     try:
#         # We need to run this in an async context
#         import asyncio
#         return asyncio.run(_async_process_message(message_id))
        
#     except Exception as e:
#         logger.error(f"Error processing message {message_id}: {str(e)}")
#         return {
#             "status": "error",
#             "reason": str(e),
#             "message_id": message_id
#         }


# @celery_app.task(name="process_pending_messages")
# def process_pending_messages(limit: int = 50) -> Dict[str, Any]:
#     """NOT USED - Process pending messages that haven't been ingested to Mem0.
    
#     Args:
#         limit: Maximum number of messages to process
        
#     Returns:
#         Processing results dictionary
#     """
#     try:
#         # We need to run this in an async context
#         import asyncio
#         return asyncio.run(_async_process_pending_messages(limit))
        
#     except Exception as e:
#         logger.error(f"Error processing pending messages: {str(e)}")
#         return {
#             "status": "error",
#             "reason": str(e)
#         }


# @celery_app.task(name="process_conversation")
# def process_conversation(conversation_id: str) -> Dict[str, Any]:
#     """NOT USED - Process all messages in a conversation.
    
#     Args:
#         conversation_id: ID of the conversation to process
        
#     Returns:
#         Processing results dictionary
#     """
#     try:
#         # We need to run this in an async context
#         import asyncio
#         return asyncio.run(_async_process_conversation(conversation_id))
        
#     except Exception as e:
#         logger.error(f"Error processing conversation {conversation_id}: {str(e)}")
#         return {
#             "status": "error",
#             "reason": str(e),
#             "conversation_id": conversation_id
#         }


# @celery_app.task(name="summarize_conversation")
# def summarize_conversation(conversation_id: str) -> Dict[str, Any]:
#     """NOT USED - Generate a summary for a conversation.
    
#     Args:
#         conversation_id: ID of the conversation to summarize
        
#     Returns:
#         Summarization results dictionary
#     """
#     try:
#         # We need to run this in an async context
#         import asyncio
#         return asyncio.run(_async_summarize_conversation(conversation_id))
        
#     except Exception as e:
#         logger.error(f"Error summarizing conversation {conversation_id}: {str(e)}")
#         return {
#             "status": "error",
#             "reason": str(e),
#             "conversation_id": conversation_id
#         }


# async def _async_process_message(message_id: str) -> Dict[str, Any]:
#     """Async implementation of process_chat_message."""
#     async with get_async_session() as db:
#         # Get message
#         query = select(ChatMessage).where(ChatMessage.id == message_id)
#         result = await db.execute(query)
#         message = result.scalars().first()
        
#         if not message:
#             return {
#                 "status": "error",
#                 "reason": "message_not_found",
#                 "message_id": message_id
#             }
        
#         # Create services
#         memory_service = MemoryService()
#         ingestion_service = ChatMem0Ingestion(db, memory_service)
        
#         # Process message
#         return await ingestion_service.process_message(message)


# async def _async_process_pending_messages(limit: int = 50) -> Dict[str, Any]:
#     """Async implementation of process_pending_messages."""
#     async with get_async_session() as db:
#         # Create services
#         memory_service = MemoryService()
#         ingestion_service = ChatMem0Ingestion(db, memory_service)
        
#         # Process pending messages
#         return await ingestion_service.process_pending_messages(limit)


# async def _async_process_conversation(conversation_id: str) -> Dict[str, Any]:
#     """Async implementation of process_conversation."""
#     async with get_async_session() as db:
#         # Create services
#         memory_service = MemoryService()
#         ingestion_service = ChatMem0Ingestion(db, memory_service)
        
#         # Process conversation
#         return await ingestion_service.process_conversation(conversation_id)


# async def _async_summarize_conversation(conversation_id: str) -> Dict[str, Any]:
#     """Async implementation of summarize_conversation."""
#     async with get_async_session() as db:
#         # Get conversation
#         query = select(Conversation).where(Conversation.id == conversation_id)
#         result = await db.execute(query)
#         conversation = result.scalars().first()
        
#         if not conversation:
#             return {
#                 "status": "error",
#                 "reason": "conversation_not_found",
#                 "conversation_id": conversation_id
#             }
        
#         # Import the summarization service
#         from app.services.conversation.summarization import ConversationSummarizationService
#         from app.services.memory import MemoryService
        
#         # Create the summarization service
#         memory_service = MemoryService()
#         summarization_service = ConversationSummarizationService(db, memory_service)
        
#         # Generate summary
#         return await summarization_service.generate_summary(conversation_id) 