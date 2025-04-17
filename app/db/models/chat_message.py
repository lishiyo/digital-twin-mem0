from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ChatMessage(Base):
    """Model for storing chat messages between users and their digital twins."""
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(String(50))  # "user" or "assistant"
    
    # Metadata
    is_stored_in_mem0: Mapped[bool] = mapped_column(default=False)
    mem0_memory_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    importance_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    
    # Relationships
    user = relationship("User", back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, turn={self.turn})>"
