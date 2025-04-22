import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.db.models.message_feedback import MessageFeedback, FeedbackType
from app.services.conversation.service import ConversationService


@pytest.fixture
def mock_db_session():
    """Mock the database session."""
    session = AsyncMock(spec=AsyncSession)
    
    # Configure the execute method to return a result
    mock_result = MagicMock()
    session.execute.return_value = mock_result
    
    # Configure the scalars and all methods on the result
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    
    return session


@pytest.fixture
def conversation_service(mock_db_session):
    """Create a ConversationService with a mock session."""
    return ConversationService(mock_db_session)


@pytest.fixture
def test_user_id():
    """Create a test user ID."""
    return "test-user-id"


@pytest.fixture
def mock_conversation(test_user_id):
    """Create a mock conversation."""
    conversation = MagicMock(spec=Conversation)
    conversation.id = str(uuid.uuid4())
    conversation.user_id = test_user_id
    conversation.title = "Test Conversation"
    conversation.created_at = datetime.now()
    conversation.updated_at = datetime.now()
    conversation.meta_data = {}
    return conversation


@pytest.fixture
def mock_message(test_user_id):
    """Create a mock message."""
    message = MagicMock(spec=ChatMessage)
    message.id = str(uuid.uuid4())
    message.content = "Test message"
    message.role = MessageRole.USER
    message.created_at = datetime.now()
    message.conversation_id = str(uuid.uuid4())
    message.user_id = test_user_id
    message.processed = False
    message.meta_data = {}
    return message


@pytest.mark.asyncio
async def test_create_conversation(conversation_service, mock_db_session, test_user_id):
    """Test creating a new conversation."""
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    
    # Setup expected return object
    mock_conversation = Conversation(
        id=str(uuid.uuid4()),
        user_id=test_user_id,
        title="Test Conversation",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        meta_data={}
    )
    mock_db_session.refresh.side_effect = lambda obj: setattr(obj, 'id', str(mock_conversation.id))
    
    # Call the service method
    result = await conversation_service.create_conversation(
        user_id=test_user_id,
        title="Test Conversation"
    )
    
    # Verify the results
    assert result is not None
    assert result.title == "Test Conversation"
    assert result.user_id == test_user_id
    
    # Verify database operations
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_get_conversation(conversation_service, mock_db_session, mock_conversation, test_user_id):
    """Test retrieving a conversation."""
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_conversation
    
    # Call the service method
    result = await conversation_service.get_conversation(mock_conversation.id, test_user_id)
    
    # Verify the results
    assert result == mock_conversation
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    query = mock_db_session.execute.call_args[0][0]
    # Check that the query contains the appropriate WHERE clauses
    query_str = str(query).lower()
    assert "where conversation.id =" in query_str
    assert "and conversation.user_id =" in query_str


@pytest.mark.asyncio
async def test_get_conversation_not_found(conversation_service, mock_db_session, test_user_id):
    """Test retrieving a non-existent conversation."""
    # Configure the mock to return None (conversation not found)
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    
    # Call the service method
    result = await conversation_service.get_conversation("non-existent-id", test_user_id)
    
    # Verify the results
    assert result is None
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_conversation(conversation_service, mock_db_session, mock_conversation, test_user_id):
    """Test updating a conversation."""
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_conversation
    
    # Call the service method
    result = await conversation_service.update_conversation(
        conversation_id=mock_conversation.id,
        user_id=test_user_id,
        title="Updated Title",
        meta_data={"key": "value"}
    )
    
    # Verify the results
    assert result is not None
    assert result.title == "Updated Title"
    assert result.meta_data == {"key": "value"}
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_conversation_not_found(conversation_service, mock_db_session, test_user_id):
    """Test updating a non-existent conversation."""
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    
    # Call the service method
    result = await conversation_service.update_conversation(
        conversation_id="non-existent-id",
        user_id=test_user_id,
        title="Updated Title"
    )
    
    # Verify the results
    assert result is None
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_conversation(conversation_service, mock_db_session, mock_conversation, test_user_id):
    """Test deleting a conversation."""
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_conversation
    
    # Call the service method
    result = await conversation_service.delete_conversation(
        conversation_id=mock_conversation.id,
        user_id=test_user_id
    )
    
    # Verify the results
    assert result is True
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    mock_db_session.delete.assert_called_once_with(mock_conversation)
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_conversation_not_found(conversation_service, mock_db_session, test_user_id):
    """Test deleting a non-existent conversation."""
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    
    # Call the service method
    result = await conversation_service.delete_conversation(
        conversation_id="non-existent-id",
        user_id=test_user_id
    )
    
    # Verify the results
    assert result is False
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    mock_db_session.delete.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_add_message(conversation_service, mock_db_session, mock_conversation, test_user_id):
    """Test creating a new message."""
    # Configure the mock for conversation lookup
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_conversation
    
    # Setup expected message ID
    message_id = str(uuid.uuid4())
    
    # Configure the mock refresh to set the id
    def mock_refresh(obj):
        if isinstance(obj, ChatMessage):
            obj.id = message_id
    
    mock_db_session.refresh.side_effect = mock_refresh
    
    # Call the service method
    message, updated_conv = await conversation_service.add_message(
        conversation_id=mock_conversation.id,
        user_id=test_user_id,
        content="Hello, world!",
        role=MessageRole.USER
    )
    
    # Verify the results
    assert message is not None
    assert message.id == message_id
    assert message.content == "Hello, world!"
    assert message.role == MessageRole.USER
    assert message.conversation_id == mock_conversation.id
    assert message.user_id == test_user_id
    assert updated_conv == mock_conversation
    
    # Verify database operations
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    assert mock_db_session.refresh.call_count == 2  # Once for message, once for conversation


@pytest.mark.asyncio
async def test_get_conversation_messages(conversation_service, mock_db_session, test_user_id):
    """Test retrieving messages for a conversation."""
    # Create mock messages
    mock_messages = [
        MagicMock(spec=ChatMessage, id=f"msg-{i}", content=f"Message {i}")
        for i in range(3)
    ]
    
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_messages
    
    # Call the service method
    result = await conversation_service.get_conversation_messages(
        conversation_id="test-conversation-id", 
        user_id=test_user_id
    )
    
    # Verify the results
    assert result == mock_messages
    assert len(result) == 3
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    query = mock_db_session.execute.call_args[0][0]
    # Check that the query contains the appropriate WHERE clauses
    query_str = str(query).lower()
    assert "where chat_message.conversation_id =" in query_str
    assert "and conversation.user_id =" in query_str


@pytest.mark.asyncio
async def test_get_user_conversations(conversation_service, mock_db_session, test_user_id):
    """Test retrieving all conversations for a user."""
    # Create mock conversations
    mock_conversations = [
        MagicMock(spec=Conversation, id=f"conv-{i}", title=f"Conversation {i}")
        for i in range(3)
    ]
    
    # Configure the mock
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_conversations
    
    # Call the service method
    result = await conversation_service.get_user_conversations(user_id=test_user_id)
    
    # Verify the results
    assert result == mock_conversations
    assert len(result) == 3
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    query = mock_db_session.execute.call_args[0][0]
    # Check that the query contains the appropriate WHERE clause
    query_str = str(query).lower()
    assert "where conversation.user_id =" in query_str


@pytest.mark.asyncio
async def test_add_feedback(conversation_service, mock_db_session, mock_message, test_user_id):
    """Test adding feedback to a message."""
    # Configure mock for message lookup
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_message
    
    # Configure feedback creation
    feedback_id = str(uuid.uuid4())
    
    def mock_refresh(obj):
        if isinstance(obj, MessageFeedback):
            obj.id = feedback_id
            obj.feedback_type = FeedbackType.HELPFUL
    
    mock_db_session.refresh.side_effect = mock_refresh
    
    # Call the service method
    feedback = await conversation_service.add_feedback(
        message_id=mock_message.id,
        user_id=test_user_id,
        feedback_type=FeedbackType.HELPFUL,
        content="Great response",
        rating=1.0
    )
    
    # Verify the results
    assert feedback is not None
    assert feedback.message_id == mock_message.id
    assert feedback.user_id == test_user_id
    assert feedback.feedback_type == FeedbackType.HELPFUL
    assert feedback.content == "Great response"
    assert feedback.rating == 1.0
    
    # Verify database operations
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_add_feedback_message_not_found(conversation_service, mock_db_session, test_user_id):
    """Test adding feedback to a non-existent message."""
    # Configure mock for message lookup - not found
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    
    # Call the service method and expect ValueError
    with pytest.raises(ValueError):
        await conversation_service.add_feedback(
            message_id="non-existent-id",
            user_id=test_user_id,
            feedback_type=FeedbackType.HELPFUL,
            content="Great response",
            rating=1.0
        )
    
    # Verify database operations
    mock_db_session.execute.assert_called_once()
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called() 