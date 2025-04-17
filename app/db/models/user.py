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
    chat_messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="user")
    proposals: Mapped[List["Proposal"]] = relationship("Proposal", back_populates="author")
    votes: Mapped[List["Vote"]] = relationship("Vote", back_populates="user") 