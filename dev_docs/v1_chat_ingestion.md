# Digital Twin Chat Ingestion System

This document outlines the architecture and implementation plan for chat storage, processing, and memory ingestion in the v1 Digital Twin system.

## Database Schema

### PostgreSQL Tables

```sql
-- Sessions/conversations table
CREATE TABLE conversation (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    context JSONB,  -- Project context, metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    summary TEXT,  -- Optional session summary
    
    -- Indexes
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_conversation_user_id (user_id),
    INDEX idx_conversation_updated_at (updated_at),
    INDEX idx_conversation_last_message (last_message_at)
);

-- Individual messages
CREATE TABLE chat_message (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    sender_type VARCHAR(10) NOT NULL, -- 'user' or 'twin'
    content TEXT NOT NULL,
    metadata JSONB, -- For confidence scores, sources, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_processed BOOLEAN DEFAULT FALSE, -- Flag for ingestion pipeline
    
    -- Indexes
    CONSTRAINT fk_conversation FOREIGN KEY (conversation_id) REFERENCES conversation(id),
    INDEX idx_message_conversation (conversation_id),
    INDEX idx_message_created_at (created_at),
    INDEX idx_message_processed (is_processed)
);

-- Optional: Message reactions/feedback
CREATE TABLE message_feedback (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL,
    user_id UUID NOT NULL,
    reaction_type VARCHAR(20) NOT NULL, -- 'helpful', 'incorrect', 'insightful', etc.
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT fk_message FOREIGN KEY (message_id) REFERENCES chat_message(id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_feedback_message (message_id)
);
```

### SQLAlchemy Models

```python
# app/db/models/conversation.py
from sqlalchemy import Column, String, JSON, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.db.base_class import Base

class Conversation(Base):
    __tablename__ = "conversation"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user={self.user_id}, title={self.title})>"


# app/db/models/chat_message.py
class ChatMessage(Base):
    __tablename__ = "chat_message"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=False)
    role: Mapped[MessageRole] = mapped_column(SQLEnum(MessageRole), nullable=False, index=True)  # 'user', 'assistant', or 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Processing status flags
    processed_in_mem0: Mapped[bool] = mapped_column(Boolean, default=False, index=True, 
                                          comment="Indicates if message has been processed through Mem0 chat ingestion")
    processed_in_summary: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                             comment="Indicates if message has been processed as part of a conversation summary")
    processed_in_graphiti: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                              comment="Indicates if message has been processed through Graphiti")
    
    # Mem0 integration fields
    is_stored_in_mem0: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                          comment="Indicates if message has been actually stored in Mem0")
    mem0_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True,
                                                 comment="Mem0 memory ID if stored in Mem0")
    importance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Graphiti integration field
    is_stored_in_graphiti: Mapped[bool] = mapped_column(Boolean, default=False, index=True,
                                              comment="Indicates if message has been actually stored in Graphiti")
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    user: Mapped["User"] = relationship("User", back_populates="messages")
    feedback: Mapped[list["MessageFeedback"]] = relationship("MessageFeedback", back_populates="message", cascade="all, delete-orphan")
    
    def needs_summarization(self) -> bool:
        """Check if message needs to be included in a summary."""
        return not self.processed_in_summary


# app/db/models/message_feedback.py
class MessageFeedback(Base):
    __tablename__ = "message_feedback"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_message.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    reaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="feedback")
    user: Mapped["User"] = relationship("User", back_populates="message_feedback")
    
    def __repr__(self):
        return f"<MessageFeedback(id={self.id}, message={self.message_id}, type={self.reaction_type})>"
```

## Session Management

### What Counts as a Session?

A "session" (implemented as a `Conversation` in our schema) represents a logical grouping of chat messages that belong together. For the Digital Twin application, we'll use a **context-based** approach:

1. **Primary Definition:** A conversation is defined by the specific project, task, or context the user is discussing with their digital twin.

2. **Session Creation Triggers:**
   - User explicitly starts a new conversation
   - System detects significant context shift (e.g., discussing a completely different project)
   - After a very long period of inactivity (e.g., 7+ days)

3. **Session Metadata:**
   - Title (auto-generated from content or user-defined)
   - Context (project ID, task IDs, other relevant context from main app)
   - Status (active, archived)

### Session Management API

```python
# app/services/conversation_service.py
from app.db.models.conversation import Conversation
from app.db.models.chat_message import ChatMessage
from app.db.session import async_session

class ConversationService:
    @staticmethod
    async def create_conversation(user_id: str, title: str = None, context: dict = None):
        async with async_session() as session:
            conversation = Conversation(
                user_id=user_id,
                title=title or "New Conversation",
                context=context or {}
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation
    
    @staticmethod
    async def get_conversations(user_id: str, limit: int = 10, offset: int = 0):
        async with async_session() as session:
            query = session.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.last_message_at.desc())
            
            total = await query.count()
            conversations = await query.limit(limit).offset(offset).all()
            
            return {
                "total": total,
                "conversations": conversations
            }
    
    @staticmethod
    async def update_conversation_title(conversation_id: str, title: str):
        async with async_session() as session:
            conversation = await session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if conversation:
                conversation.title = title
                await session.commit()
                return conversation
            return None
    
    @staticmethod
    async def add_message(conversation_id: str, sender_type: str, content: str, metadata: dict = None):
        async with async_session() as session:
            # Create and add message
            message = ChatMessage(
                conversation_id=conversation_id,
                sender_type=sender_type,
                content=content,
                metadata=metadata or {}
            )
            session.add(message)
            
            # Update conversation last_message_at
            conversation = await session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if conversation:
                conversation.last_message_at = datetime.utcnow()
                await session.commit()
                await session.refresh(message)
                return message
            
            # Rollback if conversation doesn't exist
            await session.rollback()
            return None
```

## Memory Ingestion Strategy

We'll implement a hybrid approach for chat ingestion into Mem0 and Graphiti:
1. Store individual messages as embeddings
    - Embed important individual messages (not every "thanks" or greeting)
    - Add metadata tags like session_id, timestamp, topic
    - Set TTL (time-to-live) policies to eventually expire older raw messages
2. Create periodic session summaries
    - Generate summaries at logical breakpoints (for now whenever we manually hit summarize, or every 20 messages)
        - End of sessions
        - After key decisions/insights
        - When context shifts significantly
    - Extract structured information:
        - Preferences and traits for UserProfile
        - Key decisions or commitments
        - Questions asked and answers provided
    - Store summaries in Postgres and Mem0
        - each conversation in Postgres uses the previous summary and augments it with the new messages
        - each bunch of new messages goes into Mem0
3. Implement a tiered memory system
- Short-term: Recent raw messages (high detail, recency bias)
- Medium-term: Session summaries (moderate detail, last few months)
- Long-term: Extracted facts/traits in UserProfile/Graphiti (permanent)


### 1. Individual Message Ingestion

```python
# app/services/chat_ingestion_service.py
from app.services.memory_service import MemoryService
from app.services.graphiti_service import GraphitiService
from app.db.models.chat_message import ChatMessage
from app.db.session import async_session
import asyncio

class ChatIngestionService:
    @staticmethod
    async def process_new_message(message_id: str, infer: bool = True):
        """Process a single new message for memory ingestion"""
        async with async_session() as session:
            message = await session.query(ChatMessage).filter(
                ChatMessage.id == message_id
            ).first()
            
            if not message:
                return False
            
            # Skip twin messages for now (process them in summaries)
            if message.sender_type == "twin":
                message.is_processed = True
                await session.commit()
                return True
            
            # 1. Add to Mem0 as a raw message
            if message.sender_type == "user":
                metadata = {
                    "source": "chat",
                    "source_type": "user_message",
                    "conversation_id": str(message.conversation_id),
                    "created_at": message.created_at.isoformat(),
                    **message.metadata  # Include any message-specific metadata
                }
                
                # Add to Mem0
                await MemoryService.add(
                    content=message.content,
                    user_id=message.conversation.user_id,
                    metadata=metadata,
                    infer=infer  # Whether to run inference
                )
            
            # 2. Mark as processed
            message.is_processed = True
            await session.commit()
            return True
    
    @staticmethod
    async def process_pending_messages(limit: int = 100):
        """Process a batch of pending messages"""
        async with async_session() as session:
            pending_messages = await session.query(ChatMessage).filter(
                ChatMessage.is_processed == False
            ).limit(limit).all()
            
            tasks = [
                ChatIngestionService.process_new_message(msg.id) 
                for msg in pending_messages
            ]
            
            if tasks:
                await asyncio.gather(*tasks)
            
            return len(tasks)
```

### 2. Session Summarization and Extraction

```python
# Add to chat_ingestion_service.py
from app.services.ai_service import AIService

class ChatIngestionService:
    # ... existing methods
    
    @staticmethod
    async def generate_conversation_summary(conversation_id: str):
        """Generate or update a conversation summary"""
        async with async_session() as session:
            # Get conversation and messages
            conversation = await session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                return None
            
            messages = await session.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation_id
            ).order_by(ChatMessage.created_at).all()
            
            if not messages:
                return None
            
            # Format messages for the AI
            formatted_messages = [
                f"[{msg.sender_type.upper()}]: {msg.content}" 
                for msg in messages
            ]
            
            # Generate summary
            summary = await AIService.generate_chat_summary(
                "\n".join(formatted_messages),
                conversation.context
            )
            
            # Extract key insights
            insights = await AIService.extract_profile_insights(
                "\n".join(formatted_messages),
                conversation.user_id
            )
            
            # Update conversation summary
            conversation.summary = summary
            await session.commit()
            
            # Store summary in Mem0
            await MemoryService.add(
                content=summary,
                user_id=conversation.user_id,
                metadata={
                    "source": "chat_summary",
                    "conversation_id": str(conversation_id),
                    "message_count": len(messages),
                    "created_at": datetime.utcnow().isoformat()
                },
                infer=True  # Always run inference on summaries
            )
            
            # Update user profile with insights
            if insights:
                await update_user_profile(conversation.user_id, insights)
            
            return summary
    
    @staticmethod
    async def schedule_summarization_for_active_conversations(hours_threshold: int = 24):
        """Find conversations that need summarization and schedule them"""
        async with async_session() as session:
            # Find conversations with messages newer than the last summary update
            threshold = datetime.utcnow() - timedelta(hours=hours_threshold)
            
            # Get conversations that need summarization
            conversations = await session.query(Conversation).filter(
                Conversation.updated_at > threshold,
                Conversation.status == "active"
            ).all()
            
            # Schedule summarization tasks
            for conv in conversations:
                # Use Celery to run these as background tasks
                summarize_conversation.delay(str(conv.id))
            
            return len(conversations)
```

### 3. AI Service for Processing

```python
# app/services/ai_service.py
from app.core.config import settings
import openai

class AIService:
    @staticmethod
    async def generate_chat_summary(conversation_text: str, context: dict = None):
        """Generate a summary of a conversation"""
        prompt = f"""
        Please summarize the following conversation between a user and their digital twin.
        Focus on:
        1. Key topics discussed
        2. Questions asked and answers provided
        3. Decisions or conclusions reached
        
        Additional context: {context if context else 'None provided'}
        
        Conversation:
        {conversation_text}
        
        Summary:
        """
        
        response = await openai.Completion.acreate(
            engine=settings.OPENAI_SUMMARY_MODEL,
            prompt=prompt,
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].text.strip()
    
    @staticmethod
    async def extract_profile_insights(conversation_text: str, user_id: str):
        """Extract insights about the user from conversation"""
        prompt = f"""
        Analyze the following conversation between a user and their digital twin.
        Extract insights about the user's preferences, interests, skills, and traits.
        
        For each insight, provide:
        1. The specific trait or preference
        2. The category (preference, interest, skill, relationship, dislike)
        3. A confidence score (0.0-1.0)
        4. The specific message that supports this insight
        
        Format as JSON array:
        [
            {{
                "trait": "Prefers early morning meetings",
                "category": "preference",
                "subcategory": "scheduling",
                "confidence": 0.85,
                "supporting_text": "I always schedule important meetings before 10am"
            }}
        ]
        
        Conversation:
        {conversation_text}
        
        User Insights (JSON):
        """
        
        response = await openai.Completion.acreate(
            engine=settings.OPENAI_ANALYSIS_MODEL,
            prompt=prompt,
            max_tokens=5000,
            temperature=0.2
        )
        
        try:
            # Parse JSON response
            import json
            insights = json.loads(response.choices[0].text.strip())
            return insights
        except:
            # Fallback in case of parsing error
            return []
```

## Profile Update Process

```python
# app/services/profile_update_service.py
from app.db.models.user_profile import UserProfile
from app.services.graphiti_service import GraphitiService
from app.db.session import async_session

async def update_user_profile(user_id: str, insights: list):
    """Update UserProfile and Graphiti with new insights from chat"""
    async with async_session() as session:
        # Get or create user profile
        profile = await session.query(UserProfile).filter(
            UserProfile.id == user_id
        ).first()
        
        if not profile:
            return False
        
        # Process each insight
        for insight in insights:
            category = insight.get("category", "").lower()
            trait = insight.get("trait", "")
            confidence = float(insight.get("confidence", 0.5))
            subcategory = insight.get("subcategory", "")
            
            # Skip low-confidence insights
            if confidence < 0.6:
                continue
                
            # Update appropriate profile section based on category
            if category == "preference":
                # Add to preferences if not exists or has higher confidence
                if subcategory not in profile.preferences:
                    profile.preferences[subcategory] = {}
                
                # Add or update with source and confidence
                profile.preferences[subcategory][trait] = {
                    "value": trait,
                    "confidence": confidence,
                    "source": "chat_inference",
                    "last_updated": datetime.utcnow().isoformat()
                }
                
            elif category == "interest":
                # Check if interest already exists
                existing = next((i for i in profile.interests if i.get("name") == trait), None)
                
                if existing:
                    # Update if new confidence is higher
                    if confidence > existing.get("confidence", 0):
                        existing["confidence"] = confidence
                        existing["source"] = "chat_inference"
                        existing["last_updated"] = datetime.utcnow().isoformat()
                else:
                    # Add new interest
                    profile.interests.append({
                        "name": trait,
                        "confidence": confidence,
                        "source": "chat_inference",
                        "last_updated": datetime.utcnow().isoformat()
                    })
            
            # Similar logic for skills, dislikes, etc.
            # ...
            
            # Update Graphiti knowledge graph
            await GraphitiService.update_user_trait(
                user_id=user_id,
                trait_type=category,
                trait_value=trait,
                confidence=confidence,
                source="chat_inference"
            )
        
        # Save profile updates
        await session.commit()
        return True
```

## Celery Background Tasks

```python
# app/worker.py
from app.worker_setup import celery_app
from app.services.chat_ingestion_service import ChatIngestionService

@celery_app.task
def process_chat_message(message_id: str):
    """Process a single chat message for ingestion"""
    return asyncio.run(ChatIngestionService.process_new_message(message_id))

@celery_app.task
def process_pending_chat_messages():
    """Process a batch of pending messages"""
    return asyncio.run(ChatIngestionService.process_pending_messages(limit=200))

@celery_app.task
def summarize_conversation(conversation_id: str):
    """Generate summary for a conversation"""
    return asyncio.run(ChatIngestionService.generate_conversation_summary(conversation_id))

@celery_app.task
def schedule_conversation_summaries():
    """Find and schedule conversations that need summarization"""
    return asyncio.run(ChatIngestionService.schedule_summarization_for_active_conversations())

# Schedule recurring tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Process pending messages every 5 minutes
    sender.add_periodic_task(300.0, process_pending_chat_messages.s())
    
    # Schedule conversation summaries daily
    sender.add_periodic_task(
        crontab(hour=3, minute=30),  # 3:30 AM
        schedule_conversation_summaries.s()
    )
```

## Implementation Plan

### Phase 1: Basic Chat Storage 

1. **Database Setup**
   - Create database schema (tables, indexes)
   - Implement SQLAlchemy models
   - Create Alembic migration scripts

2. **Chat Service Implementation**
   - Develop conversation CRUD operations
   - Implement message handling
   - Basic API endpoints for chat

3. **Integration with Existing Chat API**
   - Update chat API to store messages
   - Ensure backward compatibility

### Phase 2: Message Ingestion Pipeline

1. **Raw Message Ingestion**
   - Implement message processing service
   - Integrate with Mem0
   - Set up Celery tasks for background processing

2. **Basic User Profile Updates**
   - Extract simple facts from messages
   - Update user profile model
   - Tracking of metadata and confidence

### Phase 3: Advanced Summarization 

1. **Session Management**
   - Implement summarization logic
   - Develop conversation boundary detection
   - Add metadata and context handling

2. **AI Processing**
   - Build robust insight extraction
   - Implement conflict resolution
   - Add confidence scoring

### Phase 4: Optimization and Feedback

1. **Feedback Mechanisms**
   - Implement message feedback
   - Process feedback for profile updates

2. **Performance Optimization**
   - Implement database indexing strategies
   - Add caching for frequent queries
   - Develop archiving strategy for old conversations

3. **Monitoring and Evaluation**
   - Add logging and monitoring
   - Implement quality metrics for insights

## Testing Strategy

1. **Unit Testing**
   - Test database models and constraints
   - Validate service logic
   - Mock AI services for deterministic testing

2. **Integration Testing**
   - Test the full ingestion pipeline
   - Validate feedback to profile updates
   - Test with realistic chat data

3. **Performance Testing**
   - Test with high volume of messages
   - Verify scalability with many concurrent users
   - Validate batch processing efficiency 