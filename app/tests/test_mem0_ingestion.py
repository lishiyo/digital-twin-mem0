import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from datetime import datetime
import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.conversation.mem0_ingestion import ChatMem0Ingestion
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.services.memory import MemoryService

"""
NOTE: This test file contains tests for the current implementation of ChatMem0Ingestion
that uses SQLAlchemy and a direct connection to a memory service, plus older tests
(currently skipped) for a previous version that used an HTTP API.

The ChatMem0Ingestion class interface has changed from:
  - Old: ChatMem0Ingestion(api_url, api_key)
  - New: ChatMem0Ingestion(db_session, memory_service)

Skipped tests should either be updated to test the current implementation or removed.
"""


# ======== FIXTURES ========

@pytest.fixture
def mock_memory_service():
    """Create a mock MemoryService."""
    memory_service = AsyncMock(spec=MemoryService)
    memory_service.add.return_value = {"id": "test-memory-id"}
    return memory_service


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    
    # Configure mock execute method to return a mock result
    mock_result = MagicMock()
    session.execute.return_value = mock_result
    
    # Configure the scalars and all methods on the result
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    
    return session


@pytest.fixture
def mock_api_client():
    """Mock for the API client."""
    client = AsyncMock()
    
    # Configure the post method to return a successful response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "memory_id": "test-memory-id-123",
        "content": "Test content",
        "metadata": {"importance": 0.8},
        "embedding": [0.1, 0.2, 0.3]
    }
    
    client.post.return_value.__aenter__.return_value = mock_response
    return client


@pytest.fixture
def mock_message():
    """Create a mock message object."""
    message = MagicMock(spec=ChatMessage)
    message.id = "test-message-id"
    message.content = "Hello world"
    message.role = MessageRole.USER
    message.created_at = datetime.now()
    message.conversation_id = "test-conversation-id"
    message.metadata = {"test": "metadata"}
    message.user_id = "test-user-id"
    return message


@pytest.fixture
def mock_api_response():
    """Create a mock successful API response."""
    return {
        "success": True,
        "message": "Successfully processed message",
        "data": {
            "memory_id": str(uuid.uuid4()),
            "importance": 0.75,
            "topics": ["AI", "Machine Learning"],
            "summary": "A discussion about AI capabilities."
        }
    }


@pytest.fixture
def mock_api_error_response():
    """Create a mock error API response."""
    return {
        "success": False,
        "message": "Failed to process message",
        "error": "Invalid message format"
    }


@pytest.fixture
def ingestion_service(mock_db_session, mock_memory_service):
    """Create an instance of the ChatMem0Ingestion service."""
    service = ChatMem0Ingestion(mock_db_session, mock_memory_service)
    return service


# ======== INITIALIZATION TESTS ========

@pytest.mark.asyncio
async def test_init_with_db_and_memory():
    """Test initialization with required parameters."""
    db_session = AsyncMock(spec=AsyncSession)
    memory_service = AsyncMock(spec=MemoryService)
    service = ChatMem0Ingestion(db_session, memory_service)
    assert service.db == db_session
    assert service.memory_service == memory_service


@pytest.mark.asyncio
async def test_constants_defined():
    """Test that the important constants are defined."""
    db_session = AsyncMock(spec=AsyncSession)
    memory_service = AsyncMock(spec=MemoryService)
    service = ChatMem0Ingestion(db_session, memory_service)
    
    # Check that importance thresholds are defined
    assert hasattr(service, 'IMPORTANCE_THRESHOLD_HIGH')
    assert hasattr(service, 'IMPORTANCE_THRESHOLD_MEDIUM')
    
    # Check TTL constants
    assert hasattr(service, 'TTL_HIGH_IMPORTANCE')
    assert hasattr(service, 'TTL_MEDIUM_IMPORTANCE')
    assert hasattr(service, 'TTL_LOW_IMPORTANCE')


@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_init_with_default_url():
    """Test initialization with default URL."""
    service = ChatMem0Ingestion()
    assert service.api_url == "http://localhost:8000/api/memory"


@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_init_with_custom_url():
    """Test initialization with custom URL."""
    custom_url = "https://custom-mem0-api.example.com/api"
    service = ChatMem0Ingestion(api_url=custom_url)
    assert service.api_url == custom_url


@pytest.mark.skip("Test uses outdated API interface")
def test_init_service():
    """Test service initialization."""
    service = ChatMem0Ingestion(
        api_url="https://api.example.com",
        api_key="test-api-key"
    )
    
    assert service.api_url == "https://api.example.com"
    assert service.api_key == "test-api-key"
    assert service.headers == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-api-key"
    }


# ======== IMPORTANCE AND TTL CALCULATION TESTS ========

@pytest.mark.asyncio
async def test_calculate_importance(db_session: AsyncSession, mock_memory_service):
    """Test importance calculation with different message types."""
    # Create the service
    ingestion_service = ChatMem0Ingestion(db_session, mock_memory_service)
    
    # Test with a user message with no specific importance signals
    message_neutral = ChatMessage(
        id="test-message-neutral",
        conversation_id="test-conversation-id",
        user_id="test-user-id",
        role=MessageRole.USER,
        content="This is a regular message with no special importance.",
    )
    
    importance_neutral = await ingestion_service._calculate_importance(message_neutral)
    assert 0.1 <= importance_neutral <= 1.0
    
    # Test with a message containing important keywords
    message_important = ChatMessage(
        id="test-message-important",
        conversation_id="test-conversation-id",
        user_id="test-user-id",
        role=MessageRole.USER,
        content="This is important and urgent! Please don't forget to check the deadline.",
    )
    
    importance_high = await ingestion_service._calculate_importance(message_important)
    assert importance_high > importance_neutral
    
    # Test with a long message (should get length boost)
    long_content = "This is a longer message. " * 20
    message_long = ChatMessage(
        id="test-message-long",
        conversation_id="test-conversation-id",
        user_id="test-user-id",
        role=MessageRole.USER,
        content=long_content
    )
    
    importance_long = await ingestion_service._calculate_importance(message_long)
    assert importance_long > importance_neutral


@pytest.mark.asyncio
async def test_get_ttl_for_importance(db_session: AsyncSession, mock_memory_service):
    """Test the TTL determination based on importance score."""
    # Create the service
    ingestion_service = ChatMem0Ingestion(db_session, mock_memory_service)
    
    # Test low importance
    low_ttl = ingestion_service._get_ttl_for_importance(0.3)
    assert low_ttl == ingestion_service.TTL_LOW_IMPORTANCE
    
    # Test medium importance
    medium_ttl = ingestion_service._get_ttl_for_importance(0.5)
    assert medium_ttl == ingestion_service.TTL_MEDIUM_IMPORTANCE
    
    # Test high importance
    high_ttl = ingestion_service._get_ttl_for_importance(0.8)
    assert high_ttl == ingestion_service.TTL_HIGH_IMPORTANCE


# ======== PROCESS MESSAGE TESTS (ASYNC API) ========

@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_process_message_success(mock_api_client, mock_message, mock_api_response):
    """Test successful message processing."""
    # Create the service with the mock client
    service = ChatMem0Ingestion()
    service._session = mock_api_client
    
    # Process the message
    result = await service.process_message(mock_message)
    
    # Assert the result
    assert result["status"] == "success"
    assert result["memory_id"] == "test-memory-id-123"
    assert "metadata" in result
    assert result["metadata"]["importance"] == 0.8
    
    # Verify the API call
    mock_api_client.post.assert_called_once()
    _, kwargs = mock_api_client.post.call_args
    json_data = kwargs["json"]
    
    # Check that correct data was sent
    assert json_data["content"] == "Hello world"
    assert json_data["metadata"]["message_id"] == "test-message-id"
    assert json_data["metadata"]["conversation_id"] == "test-conversation-id"
    assert json_data["metadata"]["role"] == "user"


@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_process_message_http_error(mock_api_client, mock_message):
    """Test HTTP error handling during message processing."""
    # Configure the client to raise an HTTP error
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value="Internal Server Error")
    mock_api_client.post.return_value.__aenter__.return_value = mock_response
    
    # Create the service with the mock client
    service = ChatMem0Ingestion()
    service._session = mock_api_client
    
    # Process the message
    result = await service.process_message(mock_message)
    
    # Assert the result indicates failure
    assert result["status"] == "error"
    assert "Failed to process message" in result["message"]
    assert "500" in result["message"]


@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_process_message_connection_error(mock_message):
    """Test connection error handling during message processing."""
    # Create the service with a patched client that raises a connection error
    service = ChatMem0Ingestion()
    
    with patch.object(service, "_get_session") as mock_get_session:
        mock_client = AsyncMock()
        mock_client.post.side_effect = aiohttp.ClientConnectionError("Connection refused")
        mock_get_session.return_value = mock_client
        
        # Process the message
        result = await service.process_message(mock_message)
        
        # Assert the result indicates failure
        assert result["status"] == "error"
        assert "Connection error" in result["message"]


@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_process_message_timeout_error(mock_message):
    """Test timeout error handling during message processing."""
    # Create the service with a patched client that raises a timeout error
    service = ChatMem0Ingestion()
    
    with patch.object(service, "_get_session") as mock_get_session:
        mock_client = AsyncMock()
        mock_client.post.side_effect = aiohttp.ClientTimeout("Request timeout")
        mock_get_session.return_value = mock_client
        
        # Process the message
        result = await service.process_message(mock_message)
        
        # Assert the result indicates failure
        assert result["status"] == "error"
        assert "Request timeout" in result["message"]


@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_process_message_with_context(mock_api_client, mock_message):
    """Test message processing with conversation context."""
    # Create a context message
    context_message = MagicMock(spec=ChatMessage)
    context_message.content = "Previous message"
    context_message.role = MessageRole.ASSISTANT
    
    # Create the service with the mock client
    service = ChatMem0Ingestion()
    service._session = mock_api_client
    
    # Process the message with context
    result = await service.process_message(mock_message, context=[context_message])
    
    # Verify the API call included context
    _, kwargs = mock_api_client.post.call_args
    json_data = kwargs["json"]
    
    # Check that context was sent
    assert "context" in json_data
    assert len(json_data["context"]) == 1
    assert json_data["context"][0]["content"] == "Previous message"
    assert json_data["context"][0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_process_message_db(mock_db_session, mock_memory_service):
    """Test processing a single message with database interactions."""
    # Create test conversation and message
    now = datetime.now()
    conversation = Conversation(
        id="test-conversation-id",
        user_id="test-user-id",
        title="Test Conversation",
        created_at=now,
        updated_at=now
    )
    mock_db_session.add(conversation)
    
    message = ChatMessage(
        id="test-process-message",
        conversation_id="test-conversation-id",
        user_id="test-user-id",
        role=MessageRole.USER,
        content="Process this message",
        is_stored_in_mem0=False,
        created_at=now,
        meta_data={}
    )
    mock_db_session.add(message)
    
    # Setup conversation lookup
    query_result = MagicMock()
    query_result.scalars.return_value.first.return_value = conversation
    mock_db_session.execute.return_value = query_result
    
    # Setup memory service to return a specific memory ID
    mock_memory_service.add.return_value = {"id": "test-memory-id"}
    
    # Create the service
    ingestion_service = ChatMem0Ingestion(mock_db_session, mock_memory_service)
    
    # Mock the _calculate_importance method to return a fixed value
    ingestion_service._calculate_importance = AsyncMock(return_value=0.5)
    
    # Process the message
    result = await ingestion_service.process_message(message)
    
    # Verify results
    assert result["status"] == "success"
    assert result["memory_id"] == "test-memory-id"
    assert result["importance_score"] == 0.5
    
    # Verify mock calls
    mock_memory_service.add.assert_called_once()
    
    # Verify message was updated
    assert message.is_stored_in_mem0 is True
    assert message.mem0_memory_id == "test-memory-id"
    assert message.processed is True


# ======== PROCESS MESSAGE TESTS (SYNC API) ========

@pytest.mark.skip("Test uses outdated API interface")
def test_process_message_success_sync(ingestion_service, mock_message, mock_api_response):
    """Test successful message processing with synchronous API."""
    service, mock_post = ingestion_service
    
    # Setup the mock
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_api_response
    
    # Call the service method
    result = service.process_message(mock_message)
    
    # Verify the result
    assert result["success"] is True
    assert result["data"]["memory_id"] == mock_api_response["data"]["memory_id"]
    assert result["data"]["importance"] == mock_api_response["data"]["importance"]
    assert result["data"]["topics"] == mock_api_response["data"]["topics"]
    
    # Verify the API call
    mock_post.assert_called_once_with(
        f"{service.api_url}/ingest/message",
        headers=service.headers,
        json=mock_message,
        timeout=10
    )


@pytest.mark.skip("Test uses outdated API interface")
def test_process_message_error_sync(ingestion_service, mock_message, mock_api_error_response):
    """Test message processing with API error response."""
    service, mock_post = ingestion_service
    
    # Setup the mock
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = mock_api_error_response
    
    # Call the service method
    result = service.process_message(mock_message)
    
    # Verify the result
    assert result["success"] is False
    assert result["message"] == mock_api_error_response["message"]
    assert result["error"] == mock_api_error_response["error"]
    
    # Verify the API call
    mock_post.assert_called_once()


@pytest.mark.skip("Test uses outdated API interface")
def test_process_message_exception_sync(ingestion_service, mock_message):
    """Test message processing with an exception."""
    service, mock_post = ingestion_service
    
    # Setup the mock to raise an exception
    mock_post.side_effect = Exception("Connection error")
    
    # Call the service method
    result = service.process_message(mock_message)
    
    # Verify the result
    assert result["success"] is False
    assert "error" in result
    assert "Connection error" in result["error"]
    
    # Verify the API call
    mock_post.assert_called_once()


# ======== CONVERSATION PROCESSING TESTS (ASYNC API) ========

@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_process_conversation_async(mock_api_client):
    """Test processing an entire conversation."""
    # Create a list of messages
    messages = [
        MagicMock(spec=ChatMessage, id=f"msg-{i}", 
                  content=f"Message {i}", 
                  role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                  created_at=datetime.now(),
                  conversation_id="test-conversation-id",
                  metadata={})
        for i in range(3)
    ]
    
    # Create the service with the mock client
    service = ChatMem0Ingestion()
    service._session = mock_api_client
    
    # Process the conversation
    results = await service.process_conversation(messages)
    
    # Verify results
    assert len(results) == 3
    for result in results:
        assert result["status"] == "success"
        assert result["memory_id"] == "test-memory-id-123"
    
    # Verify API calls
    assert mock_api_client.post.call_count == 3


@pytest.mark.asyncio
async def test_process_conversation_db(db_session: AsyncSession, mock_memory_service):
    """Test processing all messages in a conversation using database."""
    # Create a conversation with multiple messages
    conversation = Conversation(
        id="test-conversation-full",
        user_id="test-user-id",
        title="Full Conversation Test"
    )
    db_session.add(conversation)
    
    # Create 2 unprocessed messages in this conversation
    for i in range(2):
        message = ChatMessage(
            id=f"test-conv-message-{i}",
            conversation_id="test-conversation-full",
            user_id="test-user-id",
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"Conversation message {i}",
            is_stored_in_mem0=False
        )
        db_session.add(message)
    
    await db_session.commit()
    
    # Create the service
    ingestion_service = ChatMem0Ingestion(db_session, mock_memory_service)
    
    # Mock process_message and _maybe_generate_summary
    original_process_message = ingestion_service.process_message
    ingestion_service.process_message = AsyncMock(side_effect=[
        {"status": "success", "message_id": f"test-conv-message-{i}"} 
        for i in range(2)
    ])
    ingestion_service._maybe_generate_summary = AsyncMock(return_value="Test summary")
    
    # Process the conversation
    result = await ingestion_service.process_conversation("test-conversation-full")
    
    # Verify results
    assert result["total"] == 2
    assert result["success"] == 2
    assert result["conversation_id"] == "test-conversation-full"
    
    # Verify methods were called
    assert ingestion_service.process_message.call_count == 2
    ingestion_service._maybe_generate_summary.assert_called_once_with("test-conversation-full")
    
    # Restore original method
    ingestion_service.process_message = original_process_message


@pytest.mark.asyncio
async def test_process_pending_messages(db_session: AsyncSession, mock_memory_service):
    """Test processing pending messages."""
    # Create multiple unprocessed messages
    conversation = Conversation(
        id="test-conversation-batch",
        user_id="test-user-id",
        title="Batch Test"
    )
    db_session.add(conversation)
    
    # Create 3 unprocessed messages
    for i in range(3):
        message = ChatMessage(
            id=f"test-batch-message-{i}",
            conversation_id="test-conversation-batch",
            user_id="test-user-id",
            role=MessageRole.USER,
            content=f"Batch message {i}",
            is_stored_in_mem0=False,
            processed=False
        )
        db_session.add(message)
    
    await db_session.commit()
    
    # Create the service
    ingestion_service = ChatMem0Ingestion(db_session, mock_memory_service)
    
    # Mock process_message to avoid actual processing
    original_process_message = ingestion_service.process_message
    ingestion_service.process_message = AsyncMock(side_effect=[
        {"status": "success", "message_id": f"test-batch-message-{i}"} 
        for i in range(3)
    ])
    
    # Process pending messages
    result = await ingestion_service.process_pending_messages(limit=5)
    
    # Verify results
    assert result["total"] == 3
    assert result["success"] == 3
    assert len(result["details"]) == 3
    
    # Verify process_message was called for each message
    assert ingestion_service.process_message.call_count == 3
    
    # Restore original method
    ingestion_service.process_message = original_process_message


# ======== CONVERSATION PROCESSING TESTS (SYNC API) ========

@pytest.mark.skip("Test uses outdated API interface")
def test_process_conversation_success_sync(ingestion_service, mock_message, mock_api_response):
    """Test successful conversation processing."""
    service, mock_post = ingestion_service
    
    # Create a mock conversation with multiple messages
    mock_conversation = {
        "id": str(uuid.uuid4()),
        "messages": [mock_message, mock_message, mock_message]
    }
    
    # Setup the mock
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_api_response
    
    # Call the service method
    result = service.process_conversation(mock_conversation)
    
    # Verify the result
    assert result["success"] is True
    assert "message_results" in result
    assert len(result["message_results"]) == 3
    for msg_result in result["message_results"]:
        assert msg_result["success"] is True
    
    # Verify the API call
    assert mock_post.call_count == 3


@pytest.mark.skip("Test uses outdated API interface")
def test_process_conversation_partial_success(ingestion_service, mock_message, 
                                              mock_api_response, mock_api_error_response):
    """Test conversation processing with partial success."""
    service, mock_post = ingestion_service
    
    # Create a mock conversation with multiple messages
    mock_conversation = {
        "id": str(uuid.uuid4()),
        "messages": [mock_message, mock_message, mock_message]
    }
    
    # Setup the mock to alternate between success and failure
    mock_post.side_effect = [
        MagicMock(status_code=200, json=MagicMock(return_value=mock_api_response)),
        MagicMock(status_code=400, json=MagicMock(return_value=mock_api_error_response)),
        MagicMock(status_code=200, json=MagicMock(return_value=mock_api_response))
    ]
    
    # Call the service method
    result = service.process_conversation(mock_conversation)
    
    # Verify the result
    assert result["success"] is True  # Overall success if at least one message succeeded
    assert "message_results" in result
    assert len(result["message_results"]) == 3
    assert result["message_results"][0]["success"] is True
    assert result["message_results"][1]["success"] is False
    assert result["message_results"][2]["success"] is True
    
    # Verify the API calls
    assert mock_post.call_count == 3


@pytest.mark.skip("Test uses outdated API interface")
def test_process_conversation_all_failed(ingestion_service, mock_message, mock_api_error_response):
    """Test conversation processing with all messages failing."""
    service, mock_post = ingestion_service
    
    # Create a mock conversation with multiple messages
    mock_conversation = {
        "id": str(uuid.uuid4()),
        "messages": [mock_message, mock_message, mock_message]
    }
    
    # Setup the mock to fail for all messages
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = mock_api_error_response
    
    # Call the service method
    result = service.process_conversation(mock_conversation)
    
    # Verify the result
    assert result["success"] is False  # Overall failure if all messages failed
    assert "message_results" in result
    assert len(result["message_results"]) == 3
    for msg_result in result["message_results"]:
        assert msg_result["success"] is False
    
    # Verify the API calls
    assert mock_post.call_count == 3


@pytest.mark.skip("Test uses outdated API interface")
def test_process_empty_conversation(ingestion_service):
    """Test processing a conversation with no messages."""
    service, mock_post = ingestion_service
    
    # Create a mock conversation with no messages
    mock_conversation = {
        "id": str(uuid.uuid4()),
        "messages": []
    }
    
    # Call the service method
    result = service.process_conversation(mock_conversation)
    
    # Verify the result
    assert result["success"] is False
    assert "No messages to process" in result["message"]
    
    # Verify no API calls were made
    mock_post.assert_not_called()


# ======== SESSION MANAGEMENT TESTS ========

@pytest.mark.skip("Test uses outdated API interface")
@pytest.mark.asyncio
async def test_close_session():
    """Test that the session is closed properly."""
    # Create the service with a mock session
    service = ChatMem0Ingestion()
    mock_session = AsyncMock()
    service._session = mock_session
    
    # Close the session
    await service.close()
    
    # Verify the session was closed
    mock_session.close.assert_called_once() 