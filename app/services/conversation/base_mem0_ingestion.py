import logging
from typing import Dict, List, Any, Optional, Tuple, Union

from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
import abc

logger = logging.getLogger(__name__)


class BaseChatMem0Ingestion(abc.ABC):
    """Base service for ingesting chat messages into Mem0."""
    
    # Constants for memory management
    IMPORTANCE_THRESHOLD_HIGH = 0.7
    IMPORTANCE_THRESHOLD_MEDIUM = 0.4
    TTL_HIGH_IMPORTANCE = 360  # 1 year for high importance
    TTL_MEDIUM_IMPORTANCE = 180  # 6 months for medium importance
    TTL_LOW_IMPORTANCE = 60  # 2 months for low importance
    
    def __init__(self, db_session):
        """Initialize the service.
        
        Args:
            db_session: SQLAlchemy session (sync or async)
        """
        self.db = db_session
        
    @abc.abstractmethod
    def _calculate_importance(self, message: ChatMessage) -> float:
        """Calculate importance score for a message.
        
        Args:
            message: The message to calculate importance for
            
        Returns:
            Importance score (0.0-1.0)
        """
        # Default importance by role
        base_importance = {
            MessageRole.USER: 0.5,
            MessageRole.ASSISTANT: 0.1, # super low because assistants are using already-stored memories already
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
    
    def _build_message_metadata(self, message: ChatMessage, conversation: Optional[Any]) -> Dict[str, Any]:
        """Build metadata dictionary for Mem0.
        
        Args:
            message: Chat message
            conversation: Conversation the message belongs to
            
        Returns:
            Metadata dictionary
        """
        return {
            "source": "chat",
            "role": message.role.value if hasattr(message.role, "value") else str(message.role),
            "conversation_id": message.conversation_id,
            "conversation_title": conversation.title if conversation else None,
            "message_id": message.id,
            "user_id": message.user_id,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "importance_score": message.importance_score,
            **(message.meta_data or {})  # Include any additional metadata
        }
        
    def _format_mem0_messages(self, content: str) -> List[Dict[str, str]]:
        """Format content as messages for Mem0.
        
        Args:
            content: Message content
            
        Returns:
            List of message dictionaries
        """
        return [{"role": "user", "content": str(content).strip()}] 