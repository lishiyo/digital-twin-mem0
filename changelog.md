# Changelog

## 2025-04-22: UserProfile Model Implementation

As part of our v1 migration to the personal digital twin architecture, we've implemented the UserProfile model:

### Database Changes
- Created `app/db/models/user_profile.py` with JSON fields for preferences, interests, skills, dislikes, communication style, and key relationships
- Updated User model to include a one-to-one relationship with UserProfile
- Updated IngestedDocument model to use SQLAlchemy 2.0 style with Mapped and mapped_column
- Created and applied Alembic migration to add UserProfile table and properly handle DAO table removal

### Graphiti Schema Changes
- Removed DAO-related node types (Proposal, Vote, PolicyTopic)
- Added new node types for the digital twin: Skill, Interest, Preference, Dislike, Person, TimeSlot
- Defined relationship types: HAS_SKILL, INTERESTED_IN, PREFERS, DISLIKES, KNOWS, AVAILABILITY
- Created migration script (`app/scripts/migrate_graphiti_schema.py`) with backup and rollback capabilities
- Added test data generation for validation

### TODO
- Implement saving to IngestedDocument table during file processing (currently only stored in Mem0)
- Update existing queries that work with User to utilize the new UserProfile relationship
- Test Graphiti schema changes with actual data

## 2025-04-21: Remove DAO Components

As part of our migration from v0 (DAO multi-agent) to v1 (personal digital twin) architecture, we've removed all DAO-related components:

### Database Changes
- Removed `app/db/models/proposal.py` model
- Removed `app/db/models/vote.py` model
- Removed DAO-related relationships from User model
- Created and applied Alembic migration to drop DAO tables from the database

### API Changes
- Removed `/api/v1/proposals` endpoints
- Removed proposals router from API router
- Updated README to reflect current functionality

### Graph Service Changes
- Removed Proposal and Vote entity schemas from validation logic

This is the first step in our migration to the v1 architecture, which focuses on creating a personal digital twin that can understand and represent users through multiple data sources.

Next steps:
1. Implement UserProfile model
2. Refine Graphiti schema for user traits
3. Implement chat ingestion pipeline

## 2025-04-22: Chat Log Ingestion Implementation

As part of our v1 migration to the personal digital twin architecture, we've implemented the Chat Log Ingestion system:

### Database Changes
- Created database models for `Conversation`, `ChatMessage`, and `MessageFeedback` using SQLAlchemy 2.0 style
- Implemented necessary indexes for efficient querying
- Set up proper relationships between models and the User model
- Created and applied Alembic migration to add these new tables to the database
- Fixed schema of existing `chat_message` table to use `conversation_id` instead of `session_id` and `role` instead of `sender`, and added new fields (`meta_data`, `tokens`, `processed`)

### Service Implementation
- Created `ConversationService` for CRUD operations on conversations and messages
- Implemented `ChatMem0Ingestion` service for processing chat messages into Mem0
- Added tiered memory approach with TTL policies based on message importance
- Implemented importance scoring and metadata tagging for messages
- Added proper error handling and transaction management

### Background Processing
- Set up Celery tasks for asynchronous processing of chat messages
- Implemented periodic tasks for processing pending messages
- Created task status reporting and robust error handling

### Next Steps
- Implement LLM-based entity extraction from chat logs (Task 3.1.3)
- Develop conversation boundary detection and summarization (Task 3.1.4)
- Update the chat API endpoints to use the new conversation system (Task 5.4.1) 