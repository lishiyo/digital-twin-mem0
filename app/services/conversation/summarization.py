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
        
        This uses an incremental approach:
        1. If there's an existing summary, it's preserved as context
        2. Only new unprocessed messages are summarized
        3. The new summary is combined with the existing one
        
        This ensures context from the beginning of long conversations isn't lost.
        
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
            
            # Get unprocessed messages for this conversation
            messages_query = (
                select(ChatMessage)
                .where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.processed == False
                )
                .order_by(ChatMessage.created_at)
            )
            messages_result = await self.db.execute(messages_query)
            new_messages = messages_result.scalars().all()
            
            if not new_messages:
                logger.info(f"No new messages to summarize for conversation {conversation_id}")
                return {
                    "status": "success",
                    "reason": "no_new_messages",
                    "conversation_id": conversation_id,
                    "summary": conversation.summary,
                    "title": conversation.title
                }
            
            # Format new messages for summarization
            formatted_messages = self._format_messages_for_summarization(new_messages)
            
            # Check if there's an existing summary to build upon
            existing_summary = conversation.summary
            
            # Generate summary using Gemini
            if existing_summary:
                # If we have an existing summary, we'll use it as context
                summary = await self._generate_incremental_summary_with_gemini(
                    formatted_messages, 
                    existing_summary
                )
            else:
                # First-time summary for this conversation
                summary = await self._generate_summary_with_gemini(formatted_messages)
            
            if not summary:
                logger.error(f"Failed to generate summary for conversation {conversation_id}")
                return {
                    "status": "error",
                    "reason": "summary_generation_failed",
                    "conversation_id": conversation_id
                }
            
            # Update conversation with new summary
            conversation.summary = summary
            conversation.updated_at = datetime.now(UTC)
            
            # Auto-generate title if not already set
            if not conversation.title or conversation.title.startswith("Untitled"):
                # Get a sample of messages for title generation (first few if available)
                title_messages_query = (
                    select(ChatMessage)
                    .where(ChatMessage.conversation_id == conversation_id)
                    .order_by(ChatMessage.created_at)
                    .limit(10)
                )
                title_messages_result = await self.db.execute(title_messages_query)
                title_messages = title_messages_result.scalars().all()
                
                # Format messages for title generation
                formatted_title_messages = self._format_messages_for_summarization(title_messages)
                
                # Generate title
                title = await self._generate_title_with_gemini(formatted_title_messages)
                if title:
                    conversation.title = title
            
            # Store the new summary in mem0
            meta_data = {
                "source": "conversation_summary",
                "memory_type": "summary",  # Explicitly set memory_type for UI display
                "conversation_id": conversation.id,
                "conversation_title": conversation.title,
                "message_count": len(new_messages),
                "created_at": datetime.now(UTC).isoformat(),
                "summary_type": "incremental_conversation"
            }
            
            mem0_result = await self.memory_service.add(
                content=summary,
                metadata=meta_data,
                user_id=conversation.user_id,
                ttl_days=360  # Summaries are kept for a year
            )
            
            # Mark only the new messages as processed
            for message in new_messages:
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
                "message_count": len(new_messages)
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
        """Get context from conversations for the current conversation.
        
        This function retrieves:
        1. The summary from the current conversation (if it exists) - will be summary of last 20 messages
        2. Summaries from previous other conversations
        
        This provides a continuous context including both the current conversation's 
        history and knowledge from previous conversations.
        
        Args:
            user_id: User ID
            current_conversation_id: Current conversation ID
            
        Returns:
            String containing context from current and previous conversations
        """
        try:
            context = ""
            
            # First, get the current conversation summary if it exists
            if current_conversation_id:
                current_query = select(Conversation).where(
                    Conversation.id == current_conversation_id,
                    Conversation.summary != None
                )
                current_result = await self.db.execute(current_query)
                current_conversation = current_result.scalars().first()
                
                if current_conversation and current_conversation.summary:
                    # Format current conversation summary as context
                    updated_at = current_conversation.updated_at.strftime("%Y-%m-%d %H:%M")
                    context += "Context from current conversation:\n\n"
                    context += f"Conversation: \"{current_conversation.title}\" ({updated_at})\n"
                    context += f"Summary: {current_conversation.summary}\n\n"
            
            # Then, get summaries from other conversations
            other_query = (
                select(Conversation)
                .where(
                    Conversation.user_id == user_id,
                    Conversation.id != current_conversation_id,
                    Conversation.summary != None
                )
                .order_by(desc(Conversation.updated_at))
                .limit(self.MAX_NEXT_CONVERSATION_CONTEXT)
            )
            other_result = await self.db.execute(other_query)
            other_conversations = other_result.scalars().all()
            
            if other_conversations:
                # Add a header for previous conversations if we already have current context
                if context:
                    context += "Context from previous conversations:\n\n"
                else:
                    context = "Context from previous conversations:\n\n"
                
                # Format previous conversation summaries
                for conv in other_conversations:
                    updated_at = conv.updated_at.strftime("%Y-%m-%d %H:%M")
                    context += f"Conversation: \"{conv.title}\" ({updated_at})\n"
                    context += f"Summary: {conv.summary}\n\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting conversation context for user {user_id}: {str(e)}")
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
    
    async def _generate_incremental_summary_with_gemini(self, formatted_new_messages: str, existing_summary: str) -> Optional[str]:
        """Generate an incremental summary using Gemini, building on existing summary.
        
        Args:
            formatted_new_messages: Formatted new messages to summarize
            existing_summary: Existing summary to build upon
            
        Returns:
            Updated summary or None
        """
        try:
            prompt = f"""
            I have an existing summary of a conversation, and new messages that need to be incorporated.
            
            Existing summary:
            {existing_summary}
            
            New messages to incorporate:
            {formatted_new_messages}
            
            Provide an updated comprehensive summary that includes both the information from the 
            existing summary and the key points from the new messages (these give the most recent info, so should be at the end). The summary should be coherent and read as a single continuous summary, not as two separate parts.
            
            Focus on:
            1. Maintaining all important information from the existing summary
            2. Adding key topics from the new messages
            3. Questions asked and answers provided in the new messages
            4. Any new decisions or conclusions reached
            5. Important new information shared
            
            Updated summary:
            """
            
            # Use entity extractor's Gemini model to generate summary
            response = self.entity_extractor._model.generate_content(prompt)
            
            if not response or not response.text:
                return None
                
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error generating incremental summary with Gemini: {str(e)}")
            return None 