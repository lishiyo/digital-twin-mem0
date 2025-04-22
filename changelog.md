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