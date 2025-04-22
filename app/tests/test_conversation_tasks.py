import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.conversation.tasks import (
    process_message,
    process_conversation,
    process_pending_messages
)
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation


@pytest.fixture
def mock_chat_mem0_ingestion():
    """Create a mock ChatMem0Ingestion service."""
    mock = AsyncMock()
    mock.process_message.return_value = {
        "status": "success",
        "message_id": "test-msg-id",
        "memory_id": "test-memory-id"
    }
    mock.process_conversation.return_value = {
        "status": "success",
        "conversation_id": "test-conv-id",
        "total": 2,
        "success": 2
    }
    mock.process_pending_messages.return_value = {
        "status": "success",
        "total": 3,
        "success": 3
    }
    return mock


@pytest.fixture
def mock_get_db_session():
    """Mock the get_db_session function to return a mock session."""
    session = AsyncMock()
    
    async def async_exit(*args, **kwargs):
        return None
    
    # Make the session usable as an async context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(side_effect=async_exit)
    
    return session


@patch("asyncio.run")
def test_process_message_task(mock_run):
    """Test the process_message Celery task."""
    # Configure mock to return a successful result
    mock_run.return_value = {
        "status": "success",
        "message_id": "test-msg-id",
        "memory_id": "test-memory-id"
    }
    
    # Call the task
    result = process_message("test-msg-id")
    
    # Assert the result is correct
    assert result["status"] == "success"
    assert result["message_id"] == "test-msg-id"
    assert result["memory_id"] == "test-memory-id"
    
    # Verify asyncio.run was called with the right coroutine function
    called_func_name = mock_run.call_args[0][0].__name__
    assert called_func_name == "_async_process_message"


@patch("asyncio.run")
def test_process_conversation_task(mock_run):
    """Test the process_conversation Celery task."""
    # Configure mock to return a successful result
    mock_run.return_value = {
        "status": "success",
        "conversation_id": "test-conv-id",
        "total": 2,
        "success": 2
    }
    
    # Call the task
    result = process_conversation("test-conv-id")
    
    # Assert the result is correct
    assert result["status"] == "success"
    assert result["conversation_id"] == "test-conv-id"
    assert result["total"] == 2
    assert result["success"] == 2
    
    # Verify asyncio.run was called with the right coroutine function
    called_func_name = mock_run.call_args[0][0].__name__
    assert called_func_name == "_async_process_conversation"


@patch("asyncio.run")
def test_process_pending_messages_task(mock_run):
    """Test the process_pending_messages Celery task."""
    # Configure mock to return a successful result
    mock_run.return_value = {
        "status": "success",
        "total": 3,
        "success": 3
    }
    
    # Call the task with a limit
    result = process_pending_messages(10)
    
    # Assert the result is correct
    assert result["status"] == "success"
    assert result["total"] == 3
    assert result["success"] == 3
    
    # Verify asyncio.run was called with the right coroutine function
    called_func_name = mock_run.call_args[0][0].__name__
    assert called_func_name == "_async_process_pending_messages"


@patch("asyncio.run")
def test_process_message_task_not_found(mock_run):
    """Test the process_message task when the message is not found."""
    # Configure mock to return an error result
    mock_run.return_value = {
        "status": "error",
        "reason": "message_not_found",
        "message_id": "non-existent-msg-id"
    }
    
    # Call the task
    result = process_message("non-existent-msg-id")
    
    # Assert the result is correct
    assert result["status"] == "error"
    assert "message_not_found" in result["reason"]


@patch("asyncio.run")
def test_process_message_task_error(mock_run):
    """Test the process_message task when an error occurs."""
    # Configure mock to raise an exception
    mock_run.side_effect = Exception("Test error")
    
    # Call the task
    result = process_message("test-msg-id")
    
    # Assert the result indicates an error
    assert result["status"] == "error"
    assert "Test error" in result["reason"] 