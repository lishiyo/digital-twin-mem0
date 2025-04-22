from datetime import datetime, UTC
import logging
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.conversation import Conversation
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.message_feedback import MessageFeedback, FeedbackType

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and chat messages."""
    
    def __init__(self, db_session: AsyncSession):
        """Initialize the service with a database session.
        
        Args:
            db_session: SQLAlchemy async session
        """
        self.db = db_session
    
    async def create_conversation(
        self, 
        user_id: str, 
        title: Optional[str] = None, 
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Create a new conversation.
        
        Args:
            user_id: ID of the user who owns this conversation
            title: Optional title for the conversation
            meta_data: Optional metadata dictionary
            
        Returns:
            The created Conversation object
        """
        try:
            conversation = Conversation(
                id=str(uuid4()),
                user_id=user_id,
                title=title,
                meta_data=meta_data or {},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)
            
            logger.info(f"Created conversation {conversation.id} for user {user_id}")
            return conversation
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating conversation: {str(e)}")
            raise
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """Get a conversation by ID.
        
        Args:
            conversation_id: ID of the conversation to retrieve
            user_id: ID of the user who owns the conversation (for authorization)
            
        Returns:
            The Conversation object or None if not found
        """
        try:
            query = (
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == user_id)
                .options(selectinload(Conversation.messages))
            )
            
            result = await self.db.execute(query)
            conversation = result.scalars().first()
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
            raise
    
    async def update_conversation(
        self, 
        conversation_id: str, 
        user_id: str, 
        title: Optional[str] = None, 
        summary: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Conversation]:
        """Update a conversation.
        
        Args:
            conversation_id: ID of the conversation to update
            user_id: ID of the user who owns the conversation (for authorization)
            title: New title (if provided)
            summary: New summary (if provided)
            meta_data: New metadata (if provided)
            
        Returns:
            The updated Conversation object or None if not found
        """
        try:
            conversation = await self.get_conversation(conversation_id, user_id)
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found for user {user_id}")
                return None
            
            if title is not None:
                conversation.title = title
                
            if summary is not None:
                conversation.summary = summary
                
            if meta_data is not None:
                conversation.meta_data = meta_data
                
            conversation.updated_at = datetime.now(UTC)
            
            await self.db.commit()
            await self.db.refresh(conversation)
            
            logger.info(f"Updated conversation {conversation_id}")
            return conversation
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            raise
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation.
        
        Args:
            conversation_id: ID of the conversation to delete
            user_id: ID of the user who owns the conversation (for authorization)
            
        Returns:
            True if deleted, False if not found
        """
        try:
            conversation = await self.get_conversation(conversation_id, user_id)
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found for user {user_id}")
                return False
            
            await self.db.delete(conversation)
            await self.db.commit()
            
            logger.info(f"Deleted conversation {conversation_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            raise
    
    async def add_message(
        self, 
        conversation_id: str,
        user_id: str,
        content: str,
        role: MessageRole,
        tokens: Optional[int] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[ChatMessage, Conversation]:
        """Add a new message to a conversation.
        
        Args:
            conversation_id: ID of the conversation to add the message to
            user_id: ID of the user who owns the conversation
            content: Message content
            role: Message role (user, assistant, system)
            tokens: Optional token count for the message
            meta_data: Optional metadata dictionary
            
        Returns:
            Tuple of (created message, updated conversation)
        """
        try:
            # Get or create conversation
            conversation = await self.get_conversation(conversation_id, user_id)
            
            if not conversation:
                # Create a new conversation if ID doesn't exist
                conversation = await self.create_conversation(user_id, meta_data=meta_data)
            
            # Create message
            message = ChatMessage(
                id=str(uuid4()),
                conversation_id=conversation.id,
                user_id=user_id,
                role=role,
                content=content,
                tokens=tokens,
                meta_data=meta_data or {},
                created_at=datetime.now(UTC)
            )
            
            # Update conversation timestamp
            conversation.updated_at = datetime.now(UTC)
            
            # Generate a title if this is the first user message and no title exists
            if role == MessageRole.USER and not conversation.title:
                if len(content) > 60:
                    conversation.title = content[:57] + "..."
                else:
                    conversation.title = content
            
            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)
            await self.db.refresh(conversation)
            
            logger.info(f"Added message {message.id} to conversation {conversation.id}")
            return message, conversation
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adding message to conversation {conversation_id}: {str(e)}")
            raise
    
    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages from a conversation.
        
        Args:
            conversation_id: ID of the conversation to get messages from
            user_id: ID of the user who owns the conversation (for authorization)
            limit: Maximum number of messages to return
            offset: Offset for pagination
            
        Returns:
            List of ChatMessage objects
        """
        try:
            query = (
                select(ChatMessage)
                .join(Conversation)
                .where(ChatMessage.conversation_id == conversation_id)
                .where(Conversation.user_id == user_id)
                .order_by(ChatMessage.created_at)
                .limit(limit)
                .offset(offset)
            )
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            return list(messages)
            
        except Exception as e:
            logger.error(f"Error getting messages for conversation {conversation_id}: {str(e)}")
            raise
    
    async def get_user_conversations(
        self, 
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Conversation]:
        """Get all conversations for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of conversations to return
            offset: Offset for pagination
            
        Returns:
            List of Conversation objects
        """
        try:
            query = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(desc(Conversation.updated_at))
                .limit(limit)
                .offset(offset)
            )
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            return list(conversations)
            
        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {str(e)}")
            raise
    
    async def add_feedback(
        self,
        message_id: str,
        user_id: str,
        feedback_type: FeedbackType,
        content: Optional[str] = None,
        rating: Optional[float] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> MessageFeedback:
        """Add feedback to a message.
        
        Args:
            message_id: ID of the message to add feedback to
            user_id: ID of the user providing feedback
            feedback_type: Type of feedback
            content: Optional text content for the feedback
            rating: Optional numerical rating
            meta_data: Optional metadata dictionary
            
        Returns:
            The created MessageFeedback object
        """
        try:
            # Verify message exists and belongs to this user
            query = (
                select(ChatMessage)
                .join(Conversation)
                .where(ChatMessage.id == message_id)
                .where(Conversation.user_id == user_id)
            )
            
            result = await self.db.execute(query)
            message = result.scalars().first()
            
            if not message:
                logger.warning(f"Message {message_id} not found for user {user_id}")
                raise ValueError(f"Message {message_id} not found")
            
            # Create feedback
            feedback = MessageFeedback(
                id=str(uuid4()),
                message_id=message_id,
                user_id=user_id,
                feedback_type=feedback_type,
                content=content,
                rating=rating,
                meta_data=meta_data or {},
                created_at=datetime.now(UTC)
            )
            
            self.db.add(feedback)
            await self.db.commit()
            await self.db.refresh(feedback)
            
            logger.info(f"Added feedback {feedback.id} to message {message_id}")
            return feedback
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adding feedback to message {message_id}: {str(e)}")
            raise 