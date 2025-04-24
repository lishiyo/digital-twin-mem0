from datetime import datetime, UTC
import uuid
from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import String, ForeignKey, DateTime, JSON, Text, Enum as SQLEnum, Integer, Boolean, Float, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class MessageRole(str, Enum):
    """Enum for message roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(Base):
    """Chat message model."""
    __tablename__ = "chat_message"  # Explicitly set the table name to match ForeignKey reference
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)
    # Use SQLEnum for role with lowercase values
    role: Mapped[MessageRole] = mapped_column(SQLEnum(MessageRole, values_callable=lambda x: [e.value.lower() for e in x]), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    meta_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Processing status flags
    processed_in_mem0: Mapped[bool] = mapped_column(Boolean, default=False, index=True, 
                                                comment="Indicates if message has been processed through Mem0 chat ingestion")
    processed_in_summary: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                                   comment="Indicates if message has been processed as part of a conversation summary")
    processed_in_graphiti: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                                    comment="Indicates if message has been processed through Graphiti")
    
    # Mem0 integration fields
    is_stored_in_mem0: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                                comment="Indicates if message has been actually stored in Mem0")
    mem0_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True,
                                                        comment="Mem0 memory ID if stored in Mem0")
    mem0_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    importance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Graphiti integration field
    is_stored_in_graphiti: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                                    comment="Indicates if message has been actually stored in Graphiti")
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    feedback = relationship("MessageFeedback", back_populates="message", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatMessage(id='{self.id}', conversation_id='{self.conversation_id}', role='{self.role}')>"

    def needs_summarization(self) -> bool:
        """Check if message needs to be included in a summary."""
        return not self.processed_in_summary

    def to_dict(self):
        """Convert model to dict."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tokens": self.tokens,
            "processed_in_mem0": self.processed_in_mem0,
            "processed_in_summary": self.processed_in_summary,
            "processed_in_graphiti": self.processed_in_graphiti,
            "is_stored_in_mem0": self.is_stored_in_mem0,
            "is_stored_in_graphiti": self.is_stored_in_graphiti,
            "mem0_message_id": self.mem0_message_id,
            "embedding_id": self.embedding_id,
            "meta_data": self.meta_data,
            "importance_score": self.importance_score
        }


# Add event listeners to handle enum values before insert/update
@event.listens_for(ChatMessage, 'before_insert')
def process_role_before_insert(mapper, connection, target):
    """Convert role to MessageRole enum before inserting."""
    if hasattr(target, 'role') and target.role is not None:
        if isinstance(target.role, str):
            # Try to convert string to enum
            for enum_val in MessageRole:
                if enum_val.value.lower() == target.role.lower():
                    target.role = enum_val
                    break
            else:
                # If no match found
                raise ValueError(f"Invalid role: {target.role}")

@event.listens_for(ChatMessage, 'before_update')
def process_role_before_update(mapper, connection, target):
    """Convert role to MessageRole enum before updating."""
    if hasattr(target, 'role') and target.role is not None:
        if isinstance(target.role, str):
            # Try to convert string to enum
            for enum_val in MessageRole:
                if enum_val.value.lower() == target.role.lower():
                    target.role = enum_val
                    break
            else:
                # If no match found
                raise ValueError(f"Invalid role: {target.role}")
