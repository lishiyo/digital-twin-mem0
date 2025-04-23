# Changelog

## 2025-04-26: Conversation Summarization and Context Improvements

We've made significant enhancements to the conversation summarization and context preservation system:

### Incremental Summarization
- Implemented incremental summarization that builds upon existing summaries rather than replacing them
- Added a new `_generate_incremental_summary_with_gemini` method to intelligently combine existing summaries with new content
- Fixed metadata tagging to explicitly include "memory_type": "summary" to prevent "unknown" tags in the Knowledge UI
- Enhanced prompt to ensure recent information appears at the end of summaries for better chronological organization

### Context Preservation
- Improved `get_previous_conversation_context` to include both current conversation summaries and previous conversation summaries
- Enhanced context continuity between different parts of conversations and across separate conversations
- Added clear section headers to distinguish context from current vs. previous conversations
- Ensured important information isn't lost in long-running conversations

### User Interface Improvements
- Added a "Summarize" button to the chat UI for manually triggering conversation summarization
- Implemented polling for summarization status after triggering a summary
- Added proper error handling and loading states during summarization
- Enhanced CSS styling for action buttons in the chat interface

These improvements significantly enhance the digital twin's ability to maintain context in lengthy conversations and provide continuity across multiple sessions, addressing key requirements from task 3.1.4 "Implement session management" in our v1 migration plan.

## 2025-04-25: Added User Attribute Support

To better represent user facts that don't fit existing trait categories, we've added a new "attribute" type:

### Database Updates
- Added `attributes` field to the `UserProfile` model to store user attributes like relationships and characteristics

### Entity Extraction Improvements
- Extended trait extraction prompt to include attributes in addition to skills, interests, preferences, and dislikes
- Added examples and guidance for extracting attributes like "has a husband named Kyle" or "has a cat named Aggy"

### Graph Schema Extensions
- Added "Attribute" entity type to the GraphitiService schema validation
- Implemented "HAS_ATTRIBUTE" relationship type between users and their attributes
- Set appropriate confidence thresholds for attribute extraction

This improvement allows the digital twin to more accurately represent personal characteristics and relationships that aren't skills, interests, preferences, or dislikes.

## 2025-04-25: GraphitiService Schema Validation Improvements

To address issues with entity property validation across different entity types, we've made the following improvements:

### Code Refactoring
- Added a `COMMON_OPTIONAL_FIELDS` constant to the `GraphitiService` class to share common fields across all entity types
- Simplified entity schema definitions by separating entity-specific fields from common fields
- Enhanced validation to support both older property names (e.g., "source_file") and newer ones (e.g., "source")

### Benefits
- More maintainable code with reduced duplication
- Improved flexibility when ingesting entities with different property names
- Easier addition of new common properties in the future
- Better compatibility between synchronous and asynchronous ingestion services

These changes fix property validation errors in the `GraphitiService._validate_entity_schema` method that were causing issues with entities extracted in the `_process_extracted_data` method.

## 2025-04-24: Knowledge Viewer Enhancements

As part of improving our debugging and exploration capabilities, we've enhanced the knowledge viewer interface:

### Frontend Improvements
- Added clickable memory, chat, and conversation tags with detailed modals
- Implemented memory ID tags that link directly to the corresponding memory details
- Enhanced chat tags to display message content and metadata
- Added conversation tag support to view complete conversation threads
- Improved visual styling with distinct colors for different tag types

### Backend API Additions
- Implemented `/api/v1/chat/messages/{id}` endpoint to retrieve specific chat messages
- Enhanced error handling and validation in memory retrieval endpoints
- Improved path structure consistency across APIs

These enhancements make it easier to debug memory creation and understand the relationships between chat messages, conversations, and stored memories. Users can now click on any tag to view detailed information, helping to diagnose potential duplication issues and verify correct data flow.

## 2025-04-23: Knowledge Viewer Implementation

As part of our v1 digital twin architecture, we've added a knowledge viewer interface:

### Frontend Implementation
- Created a web-based knowledge viewer UI with tabs for memories, entities, and relationships
- Implemented search and pagination for browsing large datasets
- Added detailed card views for each knowledge type with metadata display
- Integrated with the chat UI through navigation links

### Backend Updates
- Added new API endpoints for paginated listing of memories, graph nodes, and relationships
- Enhanced GraphitiService with methods for efficient data retrieval 
- Extended MemoryService with pagination support
- Created comprehensive error handling and fallbacks

This implementation provides users with a visual interface to explore their digital twin's knowledge base, making it easier to verify and understand what information the system has stored.

## 2025-04-23: Chat UI Implementation

As part of our v1 digital twin architecture, we've implemented a simple chat interface:

### Frontend Implementation
- Created a web-based chat UI using HTML, CSS, and JavaScript
- Added conversation management with sidebar for viewing conversation history  
- Implemented new conversation creation and continuing existing conversations
- Added real-time message display and response handling

### Backend Updates
- Updated FastAPI application to serve HTML templates using Jinja2
- Configured static file serving for CSS and JavaScript resources
- Added a root route (`/`) to serve the chat interface

This implementation fulfills task 5.4.4 "Add conversational UX endpoints" and provides a simple interface for testing the digital twin's conversational capabilities using the existing chat and conversation endpoints.

## 2025-04-22: Memory Ingestion Endpoints Completed

As part of our chat ingestion implementation, we've completed testing and fixing the test chat and memory endpoints described in the "Testing Chat Ingestion" section of the README:

### API Enhancements
- Fixed the memory status endpoint (`/api/v1/chat/messages/{id}/mem0-status`) to handle field name discrepancies
- Improved the memory retrieval endpoint (`/api/v1/memory/{id}`) by removing parameter confusion and redundant path segments
- Enhanced error handling for empty responses from the Mem0 API
- Added proper differentiation between processed messages and those actually stored in Mem0

### Ingestion Pipeline Improvements
- Implemented better handling of Mem0 API empty result responses
- Added logging to track message content and processing flow
- Corrected field naming inconsistencies between sync and async implementations
- Fixed memory ID handling to accurately reflect storage status in Mem0

All endpoints described in the README for testing chat ingestion now work properly, allowing for end-to-end verification of the chat ingestion pipeline.

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

## 2025-04-22: Service Refactoring and Chat API Progress

As part of our ongoing chat ingestion implementation, we've made significant improvements to the codebase:

### Service Architecture Improvements
- Refactored memory ingestion services to use inheritance with a base class (`BaseChatMem0Ingestion`)
- Created separate implementations for synchronous (`SyncChatMem0Ingestion`) and asynchronous (`ChatMem0Ingestion`) contexts
- Eliminated code duplication by moving common logic to the base class
- Fixed Celery task implementation for background processing of chat messages
- Resolved issues with async/sync database connections in Celery workers

### API Implementation Status
- Implemented the main chat endpoint (`POST /api/v1/chat`) with Mem0 ingestion
- Set up proper database transaction management and error handling
- Configured Celery tasks for asynchronous processing of chat messages

### Next Steps
- Implement remaining chat conversation endpoints (listing, viewing details)
- Add memory-specific endpoints for retrieving and managing stored memories
- Complete the conversation summarization functionality

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
