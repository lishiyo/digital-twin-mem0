from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class User(Base):
    """User model representing members in the digital twin system."""
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    handle: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    auth0_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="user")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="user")
    message_feedback: Mapped[List["MessageFeedback"]] = relationship("MessageFeedback", back_populates="user")
    profile: Mapped[Optional["UserProfile"]] = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # Removed DAO-related relationships 

    def to_dict(self):
        """Convert model to dict."""
        return {
            "id": self.id,
            "handle": self.handle,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 