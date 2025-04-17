from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLAlchemyEnum, func, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class VoteChoice(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class Vote(Base):
    """Model for storing votes on proposals by users and their digital twins."""
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("proposal.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)
    
    # Vote details
    choice: Mapped[VoteChoice] = mapped_column(SQLAlchemyEnum(VoteChoice))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 to 1.0
    is_delegate_vote: Mapped[bool] = mapped_column(Boolean, default=False)
    is_twin_vote: Mapped[bool] = mapped_column(Boolean, default=False)  # True if cast by digital twin
    
    # Graphiti integration
    graphiti_entity_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    user = relationship("User", back_populates="votes")
    proposal = relationship("Proposal", back_populates="votes") 