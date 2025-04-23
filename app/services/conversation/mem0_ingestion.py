import logging
from typing import Dict, List, Any, Optional, Tuple

from app.db.models.chat_message import ChatMessage
from app.db.models.conversation import Conversation
from app.services.memory import MemoryService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.conversation.base_mem0_ingestion import BaseChatMem0Ingestion

logger = logging.getLogger(__name__)


class ChatMem0Ingestion(BaseChatMem0Ingestion):
    """Service for ingesting chat messages into Mem0 asynchronously."""
    
    def __init__(
        self, 
        db_session: AsyncSession, 
        memory_service: MemoryService
    ):
        """Initialize the service.
        
        Args:
            db_session: SQLAlchemy async session
            memory_service: Memory service (Mem0)
        """
        super().__init__(db_session)
        self.memory_service = memory_service
    
    async def process_message(self, message: ChatMessage) -> Dict[str, Any]:
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
                message.importance_score = await self._calculate_importance(message)
            
            logger.info(f"Processing message {message.id} with importance score {message.importance_score}")
            
            # Get conversation for context
            query = (
                select(Conversation)
                .where(Conversation.id == message.conversation_id)
            )
            result = await self.db.execute(query)
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
            
            # Add to memory
            memory_result = await self.memory_service.add(
                content=message.content,
                metadata=meta_data,
                user_id=message.user_id,
                ttl_days=ttl_days
            )
            
            # Update message with Mem0 ID - use mem0_message_id for consistency with SyncChatMem0Ingestion
            message.mem0_message_id = memory_result.get("id")
            message.is_stored_in_mem0 = True
            message.processed = True
            
            await self.db.commit()
            
            logger.info(f"Successfully ingested message {message.id} to Mem0 with ID {message.mem0_message_id}")
            return {
                "status": "success",
                "memory_id": message.mem0_message_id,
                "importance_score": message.importance_score,
                "ttl_days": ttl_days,
                "message_id": message.id
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error ingesting message {message.id} to Mem0: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "message_id": message.id
            }
    
    async def process_pending_messages(self, limit: int = 50) -> Dict[str, Any]:
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
            
            result = await self.db.execute(query)
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
                process_result = await self.process_message(message)
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
    
    async def process_conversation(self, conversation_id: str) -> Dict[str, Any]:
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
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            results = {
                "total": len(messages),
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "conversation_id": conversation_id,
                "details": []
            }
            
            # Process each message
            for message in messages:
                process_result = await self.process_message(message)
                results["details"].append(process_result)
                
                if process_result["status"] == "success":
                    results["success"] += 1
                elif process_result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1
            
            # Update conversation with summary if needed
            if results["success"] > 0:
                await self._maybe_generate_summary(conversation_id)
            
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
    
    async def _calculate_importance(self, message: ChatMessage) -> float:
        """Asynchronous implementation of importance calculation."""
        return super()._calculate_importance(message)
    
    async def _maybe_generate_summary(self, conversation_id: str) -> Optional[str]:
        """Generate a summary for a conversation if needed.
        
        This is now implemented using the ConversationSummarizationService.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Generated summary or None
        """
        try:
            # Import the summarization service here to avoid circular imports
            from app.services.conversation.summarization import ConversationSummarizationService
            
            # Create the summarization service
            summarization_service = ConversationSummarizationService(self.db, self.memory_service)
            
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
            
        except Exception as e:
            logger.error(f"Error checking/generating summary for conversation {conversation_id}: {str(e)}")
            return None 