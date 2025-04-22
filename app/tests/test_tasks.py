import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.services.conversation.tasks import (
    process_message,
    process_conversation,
    process_pending_messages
)


@pytest.fixture
def mock_message():
    """Create a mock message for testing."""
    message = MagicMock(spec=ChatMessage)
    message.id = "test-process-message"
    message.content = "Test message content"
    message.role = MessageRole.USER
    message.created_at = datetime.utcnow()
    message.conversation_id = "test-conversation-id"
    message.user_id = "test-user-id"
    message.meta_data = {"source": "test"}
    message.is_stored_in_mem0 = False
    message.importance_score = 0.5
    return message


@pytest.fixture
def mock_conversation():
    """Create a mock conversation containing messages."""
    conversation = MagicMock(spec=Conversation)
    conversation.id = "test-conversation-id"
    conversation.title = "Test Conversation"
    conversation.user_id = "test-user-id"
    conversation.created_at = datetime.utcnow()
    
    # Add messages to the conversation
    message1 = MagicMock(spec=ChatMessage)
    message1.id = "test-message-1"
    message1.content = "Hello"
    message1.role = MessageRole.USER
    message1.created_at = datetime.utcnow()
    message1.is_stored_in_mem0 = False
    
    message2 = MagicMock(spec=ChatMessage)
    message2.id = "test-message-2"
    message2.content = "Hi there"
    message2.role = MessageRole.ASSISTANT
    message2.created_at = datetime.utcnow()
    message2.is_stored_in_mem0 = False
    
    conversation.messages = [message1, message2]
    return conversation


@pytest.fixture
def mock_ingestion_service():
    """Create a mock ChatMem0Ingestion service."""
    mock_service = MagicMock()
    
    # Setup process_message behavior
    async def mock_process_message(message):
        if message.id == "test-error-message":
            return {
                "status": "error",
                "reason": "Test error",
                "message_id": message.id
            }
        return {
            "status": "success",
            "memory_id": f"mem0-{uuid.uuid4()}",
            "importance_score": message.importance_score or 0.5,
            "ttl_days": 30,
            "message_id": message.id
        }
    
    # Setup process_conversation behavior
    async def mock_process_conversation(conversation_id):
        if conversation_id == "non-existent-id":
            return {
                "status": "error",
                "reason": "Conversation not found",
                "conversation_id": conversation_id,
                "total": 0,
                "success": 0,
                "skipped": 0,
                "errors": 0
            }
        
        return {
            "status": "success",
            "conversation_id": conversation_id,
            "total": 2,
            "success": 2,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
    
    mock_service.process_message = AsyncMock(side_effect=mock_process_message)
    mock_service.process_conversation = AsyncMock(side_effect=mock_process_conversation)
    mock_service.process_pending_messages = AsyncMock(return_value={
        "total": 2,
        "success": 2,
        "skipped": 0, 
        "errors": 0,
        "details": []
    })
    
    return mock_service


@patch("app.services.conversation.conversation_tasks.get_async_session")
@patch("app.services.conversation.conversation_tasks.MemoryService")
@patch("app.services.conversation.conversation_tasks.ChatMem0Ingestion")
@patch("app.services.conversation.conversation_tasks.select")
async def test_process_message(
    mock_select, 
    mock_ingestion_class, 
    mock_memory_service,
    mock_get_session,
    mock_message
):
    """Test processing a message."""
    # Setup mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_session.return_value.__aenter__.return_value = mock_db
    
    mock_result = AsyncMock()
    mock_result.scalars.return_value.first.return_value = mock_message
    mock_db.execute.return_value = mock_result
    
    mock_ingestion = mock_ingestion_class.return_value
    mock_ingestion.process_message.return_value = {
        "status": "success",
        "memory_id": "mem0-id-123",
        "importance_score": 0.5,
        "ttl_days": 30,
        "message_id": mock_message.id
    }
    
    # Call the task
    result = await process_message(mock_message.id)
    
    # Verify results
    assert result["status"] == "success"
    assert result["message_id"] == mock_message.id
    mock_ingestion.process_message.assert_called_once_with(mock_message)


@patch("app.services.conversation.conversation_tasks.get_async_session")
@patch("app.services.conversation.conversation_tasks.MemoryService")
@patch("app.services.conversation.conversation_tasks.ChatMem0Ingestion")
async def test_process_conversation_with_id(
    mock_ingestion_class,
    mock_memory_service,
    mock_get_session,
    mock_conversation
):
    """Test processing a conversation by ID."""
    # Setup mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_session.return_value.__aenter__.return_value = mock_db
    
    mock_ingestion = mock_ingestion_class.return_value
    mock_ingestion.process_conversation.return_value = {
        "status": "success",
        "conversation_id": mock_conversation.id,
        "total": 2,
        "success": 2,
        "skipped": 0,
        "errors": 0,
        "details": []
    }
    
    # Call the task
    result = await process_conversation(mock_conversation.id)
    
    # Verify results
    assert result["status"] == "success"
    assert result["conversation_id"] == mock_conversation.id
    assert result["success"] == 2
    mock_ingestion.process_conversation.assert_called_once_with(mock_conversation.id)


@patch("app.services.conversation.conversation_tasks.get_async_session")
@patch("app.services.conversation.conversation_tasks.MemoryService")
@patch("app.services.conversation.conversation_tasks.ChatMem0Ingestion")
async def test_process_conversation_failure(
    mock_ingestion_class,
    mock_memory_service,
    mock_get_session
):
    """Test processing a non-existent conversation."""
    # Setup mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_session.return_value.__aenter__.return_value = mock_db
    
    mock_ingestion = mock_ingestion_class.return_value
    mock_ingestion.process_conversation.return_value = {
        "status": "error",
        "reason": "Conversation not found",
        "conversation_id": "non-existent-id",
        "total": 0,
        "success": 0,
        "skipped": 0,
        "errors": 0
    }
    
    # Call the task
    result = await process_conversation("non-existent-id")
    
    # Verify results
    assert result["status"] == "error"
    assert "Conversation not found" in result["reason"]
    mock_ingestion.process_conversation.assert_called_once_with("non-existent-id")


@patch("app.services.conversation.conversation_tasks.get_async_session")
@patch("app.services.conversation.conversation_tasks.MemoryService")
@patch("app.services.conversation.conversation_tasks.ChatMem0Ingestion")
@patch("app.services.conversation.conversation_tasks.select")
async def test_process_message_error(
    mock_select, 
    mock_ingestion_class, 
    mock_memory_service,
    mock_get_session,
    mock_message
):
    """Test error handling when processing a message."""
    # Setup mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_session.return_value.__aenter__.return_value = mock_db
    
    mock_result = AsyncMock()
    mock_result.scalars.return_value.first.return_value = mock_message
    mock_db.execute.return_value = mock_result
    
    mock_ingestion = mock_ingestion_class.return_value
    mock_ingestion.process_message.side_effect = Exception("Test error")
    
    # Call the task
    result = await process_message(mock_message.id)
    
    # Verify results
    assert result["status"] == "error"
    assert "Test error" in result["reason"]
    assert result["message_id"] == mock_message.id
    mock_ingestion.process_message.assert_called_once_with(mock_message)


@patch("app.services.conversation.conversation_tasks.get_async_session")
@patch("app.services.conversation.conversation_tasks.MemoryService")
@patch("app.services.conversation.conversation_tasks.ChatMem0Ingestion")
async def test_process_pending_messages(
    mock_ingestion_class,
    mock_memory_service,
    mock_get_session
):
    """Test processing pending messages."""
    # Setup mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_get_session.return_value.__aenter__.return_value = mock_db
    
    mock_ingestion = mock_ingestion_class.return_value
    mock_ingestion.process_pending_messages.return_value = {
        "total": 3,
        "success": 2,
        "skipped": 1,
        "errors": 0,
        "details": []
    }
    
    # Call the task
    result = await process_pending_messages(limit=10)
    
    # Verify results
    assert result["total"] == 3
    assert result["success"] == 2
    assert result["skipped"] == 1
    mock_ingestion.process_pending_messages.assert_called_once_with(10) 