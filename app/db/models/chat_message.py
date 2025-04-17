from sqlalchemy import Column, Integer, String, Text

from app.db.base import Base


class ChatMessage(Base):
    """Model for storing chat messages between users and their digital twins."""

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    sender = Column(String(50), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    turn = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, turn={self.turn})>"
