from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime

# Import Base from base_class.py
from app.db.base_class import Base

# Import all models here
from app.db.models.user import User
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.db.models.message_feedback import MessageFeedback, FeedbackType
from app.db.models.ingested_document import IngestedDocument
from app.db.models.user_profile import UserProfile
# Add additional models as they are created

# Add common functionality to all models
setattr(Base, 'created_at', Column(DateTime, default=datetime.utcnow, nullable=False))
setattr(Base, 'updated_at', Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False))

def dict_method(self) -> dict[str, Any]:
    """Return model as dict."""
    return {c.name: getattr(self, c.name) for c in self.__table__.columns}

setattr(Base, 'dict', dict_method)
