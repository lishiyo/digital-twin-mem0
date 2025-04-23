import logging
from typing import Dict, List, Any, Optional, Tuple
import uuid

from app.db.models.chat_message import ChatMessage
from app.db.models.conversation import Conversation
from app.services.memory import MemoryClient
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.config import settings
from app.services.conversation.base_mem0_ingestion import BaseChatMem0Ingestion

logger = logging.getLogger(__name__)


class SyncChatMem0Ingestion(BaseChatMem0Ingestion):
    """Service for ingesting chat messages into Mem0 synchronously."""
    
    def __init__(self, db_session: Session):
        """Initialize the service.
        
        Args:
            db_session: SQLAlchemy synchronous session
        """
        super().__init__(db_session)
        
        # Initialize the Mem0 client directly
        api_key = settings.MEM0_API_KEY
        if not api_key:
            logger.warning("MEM0_API_KEY not set, memory functions will not work correctly")
        
        self.mem0_client = MemoryClient(api_key=api_key)
    
    def process_message(self, message: ChatMessage) -> Dict[str, Any]:
        """Process a chat message and ingest it into Mem0.
        
        Args:
            message: The ChatMessage to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            if message.is_stored_in_mem0:
                logger.info(f"Message {message.id} already ingested to Mem0")
                return {
                    "status": "skipped",
                    "reason": "already_ingested",
                    "message_id": message.id
                }
            
            # Calculate importance score if not already set
            if message.importance_score is None:
                message.importance_score = self._calculate_importance(message)
            
            logger.info(f"Processing message {message.id}: {message.content} with importance score {message.importance_score}")
            
            # Get conversation for context
            query = (
                select(Conversation)
                .where(Conversation.id == message.conversation_id)
            )
            result = self.db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                logger.error(f"Conversation {message.conversation_id} not found for message {message.id}")
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "message_id": message.id
                }
            
            # Build metadata using base class method
            meta_data = self._build_message_metadata(message, conversation)
            
            # Determine TTL based on importance
            ttl_days = self._get_ttl_for_importance(message.importance_score)
            
            # Get formatted messages for Mem0
            messages = self._format_mem0_messages(message.content)
            
            # Add to memory using the synchronous Mem0 client
            raw_result = self.mem0_client.add(
                messages, 
                user_id=message.user_id, 
                metadata=meta_data,
                version="v2",
                output_format="v1.1",
                ttl_days=ttl_days
            )
            
            # Process the result to handle different response formats
            memory_id = None
            if isinstance(raw_result, dict):
                # Handle v2 API format which returns {'results': [...]}
                if "results" in raw_result and raw_result["results"]:
                    result_obj = raw_result["results"][0]
                    memory_id = result_obj.get("id") or result_obj.get("memory_id")
                # Direct response format (v1)
                elif "memory_id" in raw_result:
                    memory_id = raw_result["memory_id"]
                elif "id" in raw_result:
                    memory_id = raw_result["id"]
                # Handle empty results array case
                elif "results" in raw_result and not raw_result["results"]:
                    # Don't generate a memory ID since Mem0 decided not to store it
                    memory_id = None
                    logger.info(f"Mem0 returned empty results array - content not stored in Mem0")
            
            # Update message with Mem0 ID
            message.mem0_message_id = memory_id
            # Mark as processed regardless of whether storage succeeded
            message.processed = True
            # Set is_stored_in_mem0 based on whether we got a memory ID
            message.is_stored_in_mem0 = memory_id is not None
            
            self.db.commit()
            
            logger.info(f"Successfully ingested message {message.id} to Mem0 with ID {memory_id}")
            return {
                "status": "success",
                "memory_id": memory_id,
                "importance_score": message.importance_score,
                "ttl_days": ttl_days,
                "message_id": message.id
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ingesting message {message.id} to Mem0: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "message_id": message.id
            }
    
    def process_pending_messages(self, limit: int = 50) -> Dict[str, Any]:
        """Process pending messages that haven't been ingested to Mem0.
        
        Args:
            limit: Maximum number of messages to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Find unprocessed messages
            query = (
                select(ChatMessage)
                .where(ChatMessage.is_stored_in_mem0 == False)
                .where(ChatMessage.processed == False)
                .limit(limit)
            )
            
            result = self.db.execute(query)
            messages = result.scalars().all()
            
            results = {
                "total": len(messages),
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "details": []
            }
            
            # Process each message
            for message in messages:
                process_result = self.process_message(message)
                results["details"].append(process_result)
                
                if process_result["status"] == "success":
                    results["success"] += 1
                elif process_result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing pending messages: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "total": 0,
                "success": 0,
                "skipped": 0,
                "errors": 0
            }
    
    def process_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Process all messages in a conversation.
        
        Args:
            conversation_id: ID of the conversation to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Find unprocessed messages in the conversation
            query = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .where(ChatMessage.is_stored_in_mem0 == False)
            )
            
            result = self.db.execute(query)
            messages = result.scalars().all()
            
            results = {
                "total": len(messages),
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "conversation_id": conversation_id,
                "details": []
            }

            logger.info(f"Processing {len(messages)} messages for conversation {conversation_id}")
            
            # Process each message
            for message in messages:
                process_result = self.process_message(message)
                results["details"].append(process_result)
                
                if process_result["status"] == "success":
                    results["success"] += 1
                elif process_result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1
            
            # Update conversation with summary if needed
            if results["success"] > 0:
                self._maybe_generate_summary(conversation_id)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing conversation {conversation_id}: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "total": 0,
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "conversation_id": conversation_id
            }
    
    def _maybe_generate_summary(self, conversation_id: str) -> Optional[str]:
        """Generate a summary for a conversation if needed.
        
        This is now implemented using the ConversationSummarizationService.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Generated summary or None
        """
        try:
            # Import needed modules
            import asyncio
            from app.services.conversation.summarization import ConversationSummarizationService
            from app.services.memory.service import MemoryService
            from app.db.session import get_async_session
            
            # We need to run this in an async context
            async def check_and_summarize():
                async with get_async_session() as async_db:
                    memory_service = MemoryService(async_db)
                    summarization_service = ConversationSummarizationService(async_db, memory_service)
                    
                    # Check if we should summarize this conversation
                    should_summarize = await summarization_service.should_summarize_conversation(conversation_id)
                    
                    if should_summarize:
                        logger.info(f"Auto-summarizing conversation {conversation_id} because it has enough new messages")
                        
                        # Generate summary directly
                        result = await summarization_service.generate_summary(conversation_id)
                        
                        if result["status"] == "success":
                            logger.info(f"Successfully auto-summarized conversation {conversation_id}")
                            return result["summary"]
                        else:
                            logger.warning(f"Failed to auto-summarize conversation {conversation_id}: {result.get('reason', 'unknown')}")
                    
                    return None
            
            # Run in new event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(check_and_summarize())
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error checking/generating summary for conversation {conversation_id}: {str(e)}")
            return None
        
    def _calculate_importance(self, message: ChatMessage) -> float:
        """Synchronous implementation of importance calculation."""
        return super()._calculate_importance(message) 