from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

# Import all models so that Base has them before running Alembic
from app.db.base_class import Base

# Import all models here
from app.db.models.user import User
from app.db.models.chat_message import ChatMessage
# Removed DAO-related models
from app.db.models.ingested_document import IngestedDocument
# Add additional models as they are created

class Base(DeclarativeBase):
    """Base class for all models."""

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate __tablename__ automatically from class name."""
        return cls.__name__.lower()

    # Add created_at and updated_at to all models
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def dict(self) -> dict[str, Any]:
        """Return model as dict."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
