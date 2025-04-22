from datetime import datetime, UTC
import uuid
from sqlalchemy import String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List

from app.db.base_class import Base


class Conversation(Base):
    """Conversation model for chat sessions."""
    __tablename__ = "conversation"  # Explicitly set the table name
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"))
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), 
                                               default=lambda: datetime.now(UTC),
                                               onupdate=lambda: datetime.now(UTC))
    meta_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Define relationships
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
    user = relationship("User", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation(id='{self.id}', user_id='{self.user_id}', title='{self.title}')>"
    
    def to_dict(self):
        """Convert model to dict."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "meta_data": self.meta_data
        } 