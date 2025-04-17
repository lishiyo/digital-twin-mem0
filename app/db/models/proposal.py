from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SQLAlchemyEnum, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    VOTING = "voting"
    PASSED = "passed"
    FAILED = "failed"
    IMPLEMENTED = "implemented"


class Proposal(Base):
    """Model for DAO proposals that can be voted on by users and their digital twins."""
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)
    
    # Status and timing
    status: Mapped[ProposalStatus] = mapped_column(
        SQLAlchemyEnum(ProposalStatus), default=ProposalStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    voting_starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voting_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        default=lambda: datetime.now() + timedelta(hours=72)  # 72-hour default timeout
    )
    
    # Quorum tracking
    total_votes: Mapped[int] = mapped_column(Integer, default=0)
    quorum_reached: Mapped[bool] = mapped_column(default=False)
    
    # Graphiti integration
    graphiti_entity_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    author = relationship("User", back_populates="proposals")
    votes = relationship("Vote", back_populates="proposal", cascade="all, delete-orphan") 