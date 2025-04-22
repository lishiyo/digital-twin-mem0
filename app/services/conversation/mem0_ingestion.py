import logging
from typing import Dict, List, Any, Optional, Tuple

from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.services.memory import MemoryService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class ChatMem0Ingestion:
    """Service for ingesting chat messages into Mem0."""
    
    # Constants for memory management
    IMPORTANCE_THRESHOLD_HIGH = 0.7
    IMPORTANCE_THRESHOLD_MEDIUM = 0.4
    TTL_HIGH_IMPORTANCE = 90  # 90 days for high importance
    TTL_MEDIUM_IMPORTANCE = 30  # 30 days for medium importance
    TTL_LOW_IMPORTANCE = 14  # 14 days for low importance
    
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
        self.db = db_session
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
            
            # Prepare metadata
            meta_data = {
                "source": "chat",
                "role": message.role.value,
                "conversation_id": message.conversation_id,
                "conversation_title": conversation.title,
                "message_id": message.id,
                "user_id": message.user_id,
                "created_at": message.created_at.isoformat(),
                "importance_score": message.importance_score,
                **message.meta_data  # Include any additional metadata
            }
            
            # Determine TTL based on importance
            ttl_days = self._get_ttl_for_importance(message.importance_score)
            
            # Add to memory
            memory_result = await self.memory_service.add(
                content=message.content,
                metadata=meta_data,
                user_id=message.user_id,
                ttl_days=ttl_days
            )
            
            # Update message with Mem0 ID
            message.mem0_memory_id = memory_result.get("id")
            message.is_stored_in_mem0 = True
            message.processed = True
            
            await self.db.commit()
            
            logger.info(f"Successfully ingested message {message.id} to Mem0 with ID {message.mem0_memory_id}")
            return {
                "status": "success",
                "memory_id": message.mem0_memory_id,
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
        """Calculate importance score for a message.
        
        This is a placeholder for a more sophisticated algorithm that would consider:
        - Message length
        - Sentiment/emotion content
        - Presence of key entities (people, dates, etc.)
        - User responses (feedback)
        
        Args:
            message: The message to calculate importance for
            
        Returns:
            Importance score (0.0-1.0)
        """
        # Simple heuristic importance calculation until we implement LLM-based scoring
        
        # Default importance by role
        base_importance = {
            MessageRole.USER: 0.5,
            MessageRole.ASSISTANT: 0.4,
            MessageRole.SYSTEM: 0.7
        }.get(message.role, 0.3)
        
        # Adjust based on content length (longer might be more important)
        content_length = len(message.content)
        length_factor = min(content_length / 500, 1.0) * 0.3
        
        # Adjust based on keywords (placeholder for more sophisticated NLP)
        keyword_factor = 0.0
        important_keywords = ["meet", "schedule", "important", "deadline", "urgent", 
                             "remember", "don't forget", "need to", "critical"]
        
        for keyword in important_keywords:
            if keyword in message.content.lower():
                keyword_factor += 0.05
        
        keyword_factor = min(keyword_factor, 0.2)
        
        # Calculate final score
        importance_score = base_importance + length_factor + keyword_factor
        importance_score = min(max(importance_score, 0.1), 1.0)  # Clamp between 0.1 and 1.0
        
        return importance_score
    
    def _get_ttl_for_importance(self, importance_score: float) -> int:
        """Determine TTL (in days) based on importance score.
        
        Args:
            importance_score: Message importance (0.0-1.0)
            
        Returns:
            TTL in days
        """
        if importance_score >= self.IMPORTANCE_THRESHOLD_HIGH:
            return self.TTL_HIGH_IMPORTANCE
        elif importance_score >= self.IMPORTANCE_THRESHOLD_MEDIUM:
            return self.TTL_MEDIUM_IMPORTANCE
        else:
            return self.TTL_LOW_IMPORTANCE
    
    async def _maybe_generate_summary(self, conversation_id: str) -> Optional[str]:
        """Generate a summary for a conversation if needed.
        
        This is a placeholder for LLM-based summarization that would be implemented
        in Task 3.1.4.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Generated summary or None
        """
        # This will be implemented as part of Task 3.1.4
        # For now, just log that we would generate a summary
        logger.info(f"Would generate summary for conversation {conversation_id}")
        return None 