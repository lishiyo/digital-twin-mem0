import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from app.db.models.conversation import Conversation
from app.db.models.chat_message import ChatMessage, MessageRole
from app.services.memory import MemoryService
from app.core.config import settings
from app.services.ingestion.entity_extraction_factory import get_entity_extractor

# Set up logging
logger = logging.getLogger(__name__)

class ConversationSummarizationService:
    """Service for summarizing conversations and preserving context between sessions."""
    
    # Constants for conversation management
    MESSAGES_BEFORE_SUMMARY = 20  # Number of unsummarized messages before auto-summarization
    MAX_SUMMARY_CONTEXT_MESSAGES = 10  # Maximum number of previous messages to include for summarization
    MAX_NEXT_CONVERSATION_CONTEXT = 3  # Maximum number of previous summaries to include as context
    
    def __init__(self, db_session: AsyncSession, memory_service: Optional[MemoryService] = None):
        """Initialize the summarization service.
        
        Args:
            db_session: Database session
            memory_service: Optional memory service (if not provided, will be created)
        """
        self.db = db_session
        self.memory_service = memory_service or MemoryService()
        self.entity_extractor = get_entity_extractor()
    
    async def generate_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Generate a summary for a conversation.
        
        Args:
            conversation_id: ID of the conversation to summarize
            
        Returns:
            Dictionary with summarization results
        """
        try:
            # Get conversation
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "conversation_id": conversation_id
                }
            
            # Get messages for this conversation
            messages_query = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at)
            )
            messages_result = await self.db.execute(messages_query)
            messages = messages_result.scalars().all()
            
            if not messages:
                logger.warning(f"No messages found for conversation {conversation_id}")
                return {
                    "status": "error",
                    "reason": "no_messages",
                    "conversation_id": conversation_id
                }
            
            # Format messages for summarization
            formatted_messages = self._format_messages_for_summarization(messages)
            
            # Generate summary using Gemini
            summary = await self._generate_summary_with_gemini(formatted_messages)
            
            if not summary:
                logger.error(f"Failed to generate summary for conversation {conversation_id}")
                return {
                    "status": "error",
                    "reason": "summary_generation_failed",
                    "conversation_id": conversation_id
                }
            
            # Update conversation with summary
            conversation.summary = summary
            conversation.updated_at = datetime.now(UTC)
            
            # Auto-generate title if not already set
            if not conversation.title or conversation.title.startswith("Untitled") or conversation.title == messages[0].content[:min(50, len(messages[0].content))]:
                title = await self._generate_title_with_gemini(formatted_messages)
                if title:
                    conversation.title = title
            
            # Store the summary in mem0
            meta_data = {
                "source": "conversation_summary",
                "conversation_id": conversation.id,
                "conversation_title": conversation.title,
                "message_count": len(messages),
                "created_at": datetime.now(UTC).isoformat(),
                "summary_type": "full_conversation"
            }
            
            mem0_result = await self.memory_service.add(
                content=summary,
                metadata=meta_data,
                user_id=conversation.user_id,
                ttl_days=360  # Summaries are kept for a year
            )
            
            # Update messages as processed
            for message in messages:
                if not message.processed:
                    message.processed = True
                
                # For assistant messages, mark them as stored in mem0 so they're not stored again
                # We don't need them now that we have the summary
                if message.role == MessageRole.ASSISTANT and not message.is_stored_in_mem0:
                    message.is_stored_in_mem0 = True
            
            await self.db.commit()
            
            logger.info(f"Successfully summarized conversation {conversation_id}")
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "summary": summary,
                "title": conversation.title,
                "mem0_id": mem0_result.get("id"),
                "message_count": len(messages)
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error summarizing conversation {conversation_id}: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "conversation_id": conversation_id
            }
    
    async def generate_conversation_title(self, conversation_id: str) -> Dict[str, Any]:
        """Generate a title for a conversation.
        
        Args:
            conversation_id: ID of the conversation to title
            
        Returns:
            Dictionary with title generation results
        """
        try:
            # Get conversation
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "conversation_id": conversation_id
                }
            
            # Get messages for this conversation (limit to first 10)
            messages_query = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at)
                .limit(10)
            )
            messages_result = await self.db.execute(messages_query)
            messages = messages_result.scalars().all()
            
            if not messages:
                logger.warning(f"No messages found for conversation {conversation_id}")
                return {
                    "status": "error",
                    "reason": "no_messages",
                    "conversation_id": conversation_id
                }
            
            # Format messages for title generation
            formatted_messages = self._format_messages_for_summarization(messages)
            
            # Generate title
            title = await self._generate_title_with_gemini(formatted_messages)
            
            if not title:
                logger.error(f"Failed to generate title for conversation {conversation_id}")
                return {
                    "status": "error",
                    "reason": "title_generation_failed",
                    "conversation_id": conversation_id
                }
            
            # Update conversation with title
            conversation.title = title
            conversation.updated_at = datetime.now(UTC)
            
            await self.db.commit()
            
            logger.info(f"Successfully generated title for conversation {conversation_id}: {title}")
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "title": title
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error generating title for conversation {conversation_id}: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "conversation_id": conversation_id
            }
    
    async def should_summarize_conversation(self, conversation_id: str) -> bool:
        """Check if a conversation should be summarized based on number of unsummarized messages.
        
        Args:
            conversation_id: ID of the conversation to check
            
        Returns:
            True if the conversation should be summarized
        """
        try:
            # Get conversation
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                return False
            
            # Get count of messages that haven't been processed
            messages_query = (
                select(ChatMessage)
                .where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.processed == False
                )
            )
            messages_result = await self.db.execute(messages_query)
            unprocessed_count = len(messages_result.scalars().all())
            
            logger.info(f"Unprocessed count for conversation {conversation_id}: {unprocessed_count}")
            
            # If we have more than MESSAGES_BEFORE_SUMMARY unprocessed messages, summarize
            return unprocessed_count >= self.MESSAGES_BEFORE_SUMMARY
            
        except Exception as e:
            logger.error(f"Error checking if conversation {conversation_id} should be summarized: {str(e)}")
            return False
    
    async def get_previous_conversation_context(self, user_id: str, current_conversation_id: str) -> str:
        """Get context from previous conversations for the current conversation.
        
        This is the core of context preservation between sessions - it retrieves summaries
        from previous conversations to provide context for the current conversation.
        
        Args:
            user_id: User ID
            current_conversation_id: Current conversation ID
            
        Returns:
            String containing context from previous conversations
        """
        try:
            # Get the most recent conversation summaries for this user (excluding current)
            query = (
                select(Conversation)
                .where(
                    Conversation.user_id == user_id,
                    Conversation.id != current_conversation_id,
                    Conversation.summary != None
                )
                .order_by(desc(Conversation.updated_at))
                .limit(self.MAX_NEXT_CONVERSATION_CONTEXT)
            )
            result = await self.db.execute(query)
            recent_conversations = result.scalars().all()
            
            if not recent_conversations:
                return ""
            
            # Format previous conversation summaries as context
            context = "Context from previous conversations:\n\n"
            
            for i, conv in enumerate(recent_conversations):
                # Add conversation title and timestamp
                updated_at = conv.updated_at.strftime("%Y-%m-%d %H:%M")
                context += f"Conversation: \"{conv.title}\" ({updated_at})\n"
                context += f"Summary: {conv.summary}\n\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting previous conversation context for user {user_id}: {str(e)}")
            return ""
    
    def _format_messages_for_summarization(self, messages: List[ChatMessage]) -> str:
        """Format messages for summarization.
        
        Args:
            messages: List of messages to format
            
        Returns:
            Formatted string of messages
        """
        formatted = ""
        
        for msg in messages:
            role_display = "User" if msg.role == MessageRole.USER else "Assistant"
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            formatted += f"[{timestamp}] {role_display}: {msg.content}\n\n"
        
        return formatted
    
    async def _generate_summary_with_gemini(self, formatted_messages: str) -> Optional[str]:
        """Generate a summary using Gemini.
        
        Args:
            formatted_messages: Formatted messages to summarize
            
        Returns:
            Generated summary or None
        """
        try:
            prompt = f"""
            Please summarize the following conversation between a user and an AI assistant.
            Focus on:
            1. Key topics discussed
            2. Questions asked and answers provided
            3. Decisions or conclusions reached
            4. Any important information shared
            
            Write a concise yet comprehensive summary that captures the main points and could be used to refresh someone's memory about this conversation.
            
            Conversation:
            {formatted_messages}
            
            Summary:
            """
            
            # Use entity extractor's Gemini model to generate summary
            response = self.entity_extractor._model.generate_content(prompt)
            
            if not response or not response.text:
                return None
                
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error generating summary with Gemini: {str(e)}")
            return None
    
    async def _generate_title_with_gemini(self, formatted_messages: str) -> Optional[str]:
        """Generate a title using Gemini.
        
        Args:
            formatted_messages: Formatted messages to generate title for
            
        Returns:
            Generated title or None
        """
        try:
            prompt = f"""
            Create a short, descriptive title (maximum 50 characters) for the following conversation.
            The title should capture the main topic or purpose of the conversation.
            
            Conversation:
            {formatted_messages}
            
            Title:
            """
            
            # Use entity extractor's Gemini model to generate title
            response = self.entity_extractor._model.generate_content(prompt)
            
            if not response or not response.text:
                return None
                
            # Ensure the title is not too long
            title = response.text.strip()
            if len(title) > 50:
                title = title[:47] + "..."
                
            return title
            
        except Exception as e:
            logger.error(f"Error generating title with Gemini: {str(e)}")
            return None 