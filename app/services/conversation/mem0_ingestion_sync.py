import logging
from typing import Dict, List, Any, Optional, Tuple

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
            
            logger.info(f"Processing message {message.id} with importance score {message.importance_score}")
            
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
            
            # Update message with Mem0 ID
            message.mem0_message_id = memory_id
            message.is_stored_in_mem0 = True
            message.processed = True
            
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
        
    def _calculate_importance(self, message: ChatMessage) -> float:
        """Synchronous implementation of importance calculation."""
        return super()._calculate_importance(message) 