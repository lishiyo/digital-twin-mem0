# Changelog

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