import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime

from app.db.models.conversation import Conversation
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.message_feedback import MessageFeedback, FeedbackType
from app.db.models.user import User


@pytest.mark.asyncio
async def test_create_conversation(db_session: AsyncSession):
    """Test creating a conversation with a user."""
    # Create a test user
    user_id = "test-user-id"
    test_user = User(
        id=user_id,
        handle="testuser",
        email="test@example.com",
        is_active=True
    )
    db_session.add(test_user)
    await db_session.commit()
    
    # Create a conversation
    conversation_id = "test-conversation-id"
    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        title="Test Conversation",
        meta_data={"context": "test"}
    )
    db_session.add(conversation)
    await db_session.commit()
    
    # Query to verify
    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    fetched_conversation = result.scalars().first()
    
    assert fetched_conversation is not None
    assert fetched_conversation.id == conversation_id
    assert fetched_conversation.user_id == user_id
    assert fetched_conversation.title == "Test Conversation"
    assert fetched_conversation.meta_data == {"context": "test"}


@pytest.mark.asyncio
async def test_create_chat_message(db_session: AsyncSession):
    """Test creating a chat message in a conversation."""
    # Use the user from the previous test or create if needed
    user_id = "test-user-id"
    result = await db_session.execute(
        select(User).where(User.id == user_id)
    )
    test_user = result.scalars().first()
    
    if not test_user:
        test_user = User(
            id=user_id,
            handle="testuser",
            email="test@example.com",
            is_active=True
        )
        db_session.add(test_user)
        await db_session.commit()
    
    # Get the test conversation or create if needed
    conversation_id = "test-conversation-id"
    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalars().first()
    
    if not conversation:
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id,
            title="Test Conversation",
            meta_data={"context": "test"}
        )
        db_session.add(conversation)
        await db_session.commit()
    
    # Create a chat message
    message_id = "test-message-id"
    message = ChatMessage(
        id=message_id,
        conversation_id=conversation_id,
        user_id=user_id,
        role=MessageRole.USER,
        content="Hello, this is a test message",
        meta_data={"importance": "high"},
        tokens=10,
        is_stored_in_mem0=False
    )
    db_session.add(message)
    await db_session.commit()
    
    # Query to verify
    result = await db_session.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    fetched_message = result.scalars().first()
    
    assert fetched_message is not None
    assert fetched_message.id == message_id
    assert fetched_message.conversation_id == conversation_id
    assert fetched_message.user_id == user_id
    assert fetched_message.role == MessageRole.USER
    assert fetched_message.content == "Hello, this is a test message"
    assert fetched_message.meta_data == {"importance": "high"}
    assert fetched_message.tokens == 10
    assert not fetched_message.is_stored_in_mem0


@pytest.mark.asyncio
async def test_create_message_feedback(db_session: AsyncSession):
    """Test creating feedback for a message."""
    # Get the test message or create it if needed
    message_id = "test-message-id"
    result = await db_session.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    message = result.scalars().first()
    
    if not message:
        # If message doesn't exist, make sure we have a user and conversation first
        user_id = "test-user-id"
        conversation_id = "test-conversation-id"
        
        # Check and create user if needed
        user_result = await db_session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalars().first()
        if not user:
            user = User(
                id=user_id,
                handle="testuser",
                email="test@example.com",
                is_active=True
            )
            db_session.add(user)
            await db_session.commit()
        
        # Check and create conversation if needed
        conv_result = await db_session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalars().first()
        if not conversation:
            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title="Test Conversation",
                meta_data={"context": "test"}
            )
            db_session.add(conversation)
            await db_session.commit()
        
        # Now create the message
        message = ChatMessage(
            id=message_id,
            conversation_id=conversation_id,
            user_id=user_id,
            role=MessageRole.USER,
            content="Hello, this is a test message",
            meta_data={"importance": "high"},
            tokens=10,
            is_stored_in_mem0=False
        )
        db_session.add(message)
        await db_session.commit()
    
    # Create feedback
    feedback_id = "test-feedback-id"
    feedback = MessageFeedback(
        id=feedback_id,
        message_id=message_id,
        user_id=message.user_id,  # Use the same user who created the message
        feedback_type=FeedbackType.HELPFUL,
        rating=0.9,
        content="This was very helpful"
    )
    db_session.add(feedback)
    await db_session.commit()
    
    # Query to verify
    result = await db_session.execute(
        select(MessageFeedback).where(MessageFeedback.id == feedback_id)
    )
    fetched_feedback = result.scalars().first()
    
    assert fetched_feedback is not None
    assert fetched_feedback.id == feedback_id
    assert fetched_feedback.message_id == message_id
    assert fetched_feedback.user_id == message.user_id
    assert fetched_feedback.feedback_type == FeedbackType.HELPFUL
    assert fetched_feedback.rating == 0.9
    assert fetched_feedback.content == "This was very helpful"


@pytest.mark.asyncio
async def test_relationships(db_session: AsyncSession):
    """Test relationships between conversation, messages, and feedback."""
    # First, create a test user
    user_id = "test-user-id"
    test_user = User(
        id=user_id,
        handle="testuser",
        email="test@example.com",
        is_active=True
    )
    db_session.add(test_user)
    await db_session.commit()
    
    # Create a conversation
    conversation_id = "test-conversation-id"
    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        title="Test Conversation",
        meta_data={"context": "test"}
    )
    db_session.add(conversation)
    await db_session.commit()
    
    # Create a message
    message_id = "test-message-id"
    message = ChatMessage(
        id=message_id,
        conversation_id=conversation_id,
        user_id=user_id,
        role=MessageRole.USER,
        content="Test message for relationships",
        meta_data={"importance": "high"}
    )
    db_session.add(message)
    await db_session.commit()
    
    # Create feedback for the message
    feedback_id = "test-feedback-id"
    feedback = MessageFeedback(
        id=feedback_id,
        message_id=message_id,
        user_id=user_id,
        feedback_type=FeedbackType.HELPFUL,
        rating=0.9,
        content="Good message"
    )
    db_session.add(feedback)
    await db_session.commit()
    
    # Now test the relationships
    
    # 1. Test conversation-message relationship
    result = await db_session.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    fetched_conversation = result.scalars().first()
    
    assert fetched_conversation is not None
    assert len(fetched_conversation.messages) == 1
    assert fetched_conversation.messages[0].id == message_id
    
    # 2. Test message-feedback relationship
    result = await db_session.execute(
        select(ChatMessage)
        .where(ChatMessage.id == message_id)
        .options(selectinload(ChatMessage.feedback))
    )
    fetched_message = result.scalars().first()
    
    assert fetched_message is not None
    assert len(fetched_message.feedback) == 1
    assert fetched_message.feedback[0].id == feedback_id
    
    # 3. Test user relationships
    result = await db_session.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.conversations),
            selectinload(User.messages),
            selectinload(User.message_feedback)
        )
    )
    fetched_user = result.scalars().first()
    
    assert fetched_user is not None
    assert len(fetched_user.conversations) == 1
    assert len(fetched_user.messages) == 1
    assert len(fetched_user.message_feedback) == 1 