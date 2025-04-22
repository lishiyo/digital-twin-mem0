from datetime import datetime, UTC
import uuid
from enum import Enum
from sqlalchemy import String, ForeignKey, DateTime, JSON, Text, Enum as SQLEnum, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any

from app.db.base_class import Base


class FeedbackType(str, Enum):
    """Enum for feedback types."""
    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"
    INCORRECT = "incorrect"
    HARMFUL = "harmful"
    OTHER = "other"


class MessageFeedback(Base):
    """Feedback on messages model."""
    __tablename__ = "message_feedback"  # Explicitly set the table name
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_message.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"))
    feedback_type: Mapped[FeedbackType] = mapped_column(SQLEnum(FeedbackType))
    content: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    meta_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Define relationships
    message = relationship("ChatMessage", back_populates="feedback")
    user = relationship("User", back_populates="message_feedback")
    
    def __repr__(self):
        return f"<MessageFeedback(id='{self.id}', message_id='{self.message_id}', feedback_type='{self.feedback_type}')>"
    
    def to_dict(self):
        """Convert model to dict."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "feedback_type": self.feedback_type.value if self.feedback_type else None,
            "content": self.content,
            "rating": self.rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "meta_data": self.meta_data
        } 