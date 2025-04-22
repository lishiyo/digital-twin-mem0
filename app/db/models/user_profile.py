from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy import String, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class UserProfile(Base):
    """Model for storing comprehensive user profile information for the digital twin."""
    
    # Explicitly set table name to match existing database table
    __tablename__ = "userprofile"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), unique=True, index=True)
    
    # JSON fields for user traits and characteristics
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    interests: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    skills: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    dislikes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    communication_style: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    key_relationships: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # Metadata
    last_updated_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    user = relationship("User", back_populates="profile")
    
    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, user_id={self.user_id})>" 