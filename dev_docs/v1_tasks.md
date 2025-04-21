# Digital Twin V1 Migration Tasks

This document outlines the task breakdown for our migration from v0 (DAO multi-agent) to v1 (personal digital twin) architecture. Tasks are organized into phases with dependencies clearly marked.

## Migration Strategy Overview

We're pivoting from the DAO multi-agent approach to focus entirely on creating a faithful digital twin that can:

1. Understand user preferences, skills, interests, and relationships
2. Ingest multiple data sources to build a comprehensive user model
3. Generate personalized recommendations based on external context
4. Update its knowledge based on user feedback and interactions

The implementation is organized into 6 phases, with **phases 1-3 forming the critical path**:

## Phase 1: Foundation

### 1. Database Schema Changes

**1.1. Remove DAO-related models**
- [ ] Identify and delete `app/db/models/proposal.py` and `app/db/models/vote.py`
- [ ] Remove model imports and references in other files
- [ ] Test codebase compilation without these models

**1.2. Create UserProfile model**
- [ ] Create new file `app/db/models/user_profile.py`
- [ ] Define UserProfile class with these fields:
  - [ ] `preferences`: JSON field for user preferences
  - [ ] `interests`: JSON array of user interests
  - [ ] `skills`: JSON array of user skills
  - [ ] `dislikes`: JSON array of user dislikes
  - [ ] `communication_style`: JSON object for communication preferences
  - [ ] `key_relationships`: JSON array for important relationships
- [ ] Add proper relationship to User model
- [ ] Implement default values and type hints

**1.3. Update User model**
- [ ] Add relationship to UserProfile in `app/db/models/user.py`
- [ ] Ensure cascade delete for orphaned profiles
- [ ] Update existing queries that work with User

**1.4. Create Alembic migration**
- [ ] Generate migration: `alembic revision --autogenerate -m "remove dao models, add user profile"`
- [ ] Review and adjust generated migration
- [ ] Ensure proper upgrade and downgrade paths

**1.5. Test database migrations**
- [ ] Define overall testing strategy (unit, integration, e2e) in a new file TESTING.md 
- [ ] Setup necessary base test configurations/fixtures
- [ ] Run upgrade migration on test database
- [ ] Verify schema changes
- [ ] Test downgrade path
- [ ] Validate with actual data 

*Dependencies: 1.4 depends on 1.1, 1.2, and 1.3; 1.5 depends on 1.4*

### 2. Graphiti Schema Refinements

**2.1. Remove DAO-related node types**
- [ ] Remove Proposal, Vote, and PolicyTopic entities
- [ ] Delete associated relationship definitions
- [ ] Test schema validation without these components

**2.2. Define new node types**
- [ ] Create Skill, Interest, Preference, Dislike, Person, TimeSlot nodes
- [ ] Define properties for each node type
- [ ] Create validation logic and test data

**2.3. Define new relationship types**
- [ ] Define HAS_SKILL, INTERESTED_IN, PREFERS, DISLIKES, KNOWS, AVAILABILITY
- [ ] Add properties like proficiency, strength, recurrence
- [ ] Implement validation and test data

**2.4. Update document/event linking**
- [ ] Ensure proper connections between nodes and User
- [ ] Update existing queries
- [ ] Test with sample data

**2.5. Create migration script**
- [ ] Develop script to migrate existing Graphiti data
- [ ] Handle DAO node/edge removal
- [ ] Implement transformation logic
- [ ] Add rollback capability

**2.6. Test Graphiti schema changes**
- [ ] Run migration on test dataset
- [ ] Verify structure and relationships
- [ ] Test queries against new schema
- [ ] Validate rollback procedure

*Dependencies: 2.3 depends on 2.2; 2.5 depends on 2.1, 2.2, 2.3, and 2.4; 2.6 depends on 2.5*

### 3. Basic Chat Log Ingestion

**3.1.1. Implement chat message persistence**
- [ ] Update chat message model if needed
- [ ] Create database service for CRUD operations
- [ ] Implement transaction handling and logging

**3.1.2. Create Mem0 ingestion pipeline**
- [ ] Develop chat transformer for Mem0
- [ ] Implement metadata tagging
- [ ] Create batch processing
- [ ] Add error handling and retries

**3.1.3. Extract entity information**
- [ ] Implement LLM-based entity extraction
- [ ] Create mappers to UserProfile fields
- [ ] Develop confidence scoring
- [ ] Implement Graphiti node/relationship creation

*Dependencies: 3.1.2 and 3.1.3 depend on 3.1.1; All 3.1.x tasks depend on 1.x and 2.x*

### 4. Remove DAO Components

**4.1. Remove DAO-related agent components**
- [ ] Identify and remove DAO-related code
- [ ] Update agent configurations
- [ ] Remove DAO-specific prompts
- [ ] Test agent functionality

**5.1. Remove DAO-related endpoints**
- [ ] Remove `/proposals/*` endpoints
- [ ] Update API documentation
- [ ] Remove route handlers and services
- [ ] Test API without these endpoints

*No dependencies - these can be done independently*

## Phase 2: Core Twin Functionality

### 4.2. Agent Profile Integration

**4.2.1. Create UserProfile fetcher node**
- [ ] Develop new LangGraph node
- [ ] Implement database integration
- [ ] Add caching for performance
- [ ] Create fallbacks for missing profiles

**4.2.2. Update context synthesis logic**
- [ ] Modify `merge_context` node to include profile
- [ ] Implement priority weighting
- [ ] Create hierarchical structure
- [ ] Develop profile incorporation templates

**4.2.3. Implement confidence and recency weighting**
- [ ] Add timestamp-based sorting
- [ ] Implement confidence calculation
- [ ] Create weighted merging algorithm
- [ ] Test with various scenarios

**4.2.4. Add attribution tracking**
- [ ] Create attribution metadata schema
- [ ] Implement source tracking
- [ ] Develop attribution in responses
- [ ] Test accuracy

*Dependencies: 4.2.x depends on database schema changes (1.x)*

### 5.2. User Profile Endpoints

**5.2.1. Create GET /api/v1/profile endpoint**
- [ ] Implement route handler
- [ ] Create profile service
- [ ] Add response serialization
- [ ] Implement error handling

**5.2.2. Implement PUT /api/v1/profile**
- [ ] Create route handler for updates
- [ ] Implement validation
- [ ] Create update service
- [ ] Add concurrency control

**5.2.3. Add validation logic**
- [ ] Implement schema validation
- [ ] Create business logic validators
- [ ] Add security protections
- [ ] Implement partial updates

**5.2.4. Create response formatting**
- [ ] Design response schema with stats
- [ ] Implement stat gathering
- [ ] Add pagination
- [ ] Create detailed/summary views

*Dependencies: 5.2.x depends on database schema changes (1.x)*

### 5.4. Enhanced Chat Endpoints

**5.4.1. Update POST /api/v1/chat**
- [ ] Modify endpoint to store history
- [ ] Implement transaction handling
- [ ] Add metadata capture
- [ ] Ensure compatibility

**5.4.2. Implement Mem0 feedback loop**
- [ ] Create background task for ingestion
<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->

- [ ] Implement duplicate detection
- [ ] Add importance scoring
- [ ] Create TTL management

**5.4.3. Add background tasks for trait extraction**
- [ ] Implement task queue integration
- [ ] Create extraction service
- [ ] Develop UserProfile updates
- [ ] Add conflict resolution

*Dependencies: 5.4.x depends on chat ingestion (3.1.x)*

## Phase 3: Recommendation System

### 4.3. Recommendation Engine

**4.3.1. Create dedicated recommendation node**
- [ ] Develop new LangGraph node
- [ ] Implement configuration options
- [ ] Create I/O schema
- [ ] Add logging

**4.3.2. Implement external context analysis**
- [ ] Create parsing logic
- [ ] Implement keyword extraction
- [ ] Develop context categorization
- [ ] Add relevance scoring

**4.3.3. Develop personalized recommendation generation**
- [ ] Create prompt templates
- [ ] Implement profile-aware logic
- [ ] Add recommendation diversity
- [ ] Create the fallback loop:
    - [ ] Implement logic for the agent to detect insufficient information and generate targeted clarification questions for the user.
    - [ ] Design the agent flow to process user answers to clarification questions. The flow looks like "insufficient info -> ask clarifying question -> process answer -> end when all info collected -> generate recommendation".

**4.3.4. Add justification and confidence scoring**
- [ ] Implement reasoning generation
- [ ] Create confidence calculation
- [ ] Add source attribution
- [ ] Develop presentation formatting

*Dependencies: 4.3.x depends on agent profile integration (4.2.x)*

### 4.4. Feedback Mechanisms

**4.4.1. Create feedback collection workflow**
- [ ] Design feedback schema
- [ ] Implement UI hooks
- [ ] Create API endpoints
- [ ] Add validation

**4.4.2. Develop UserProfile update logic**
- [ ] Create update service based on feedback
- [ ] Implement preference adjustments
- [ ] Add preference discovery
- [ ] Create feedback-to-profile mapping

**4.4.3. Implement conflict resolution**
- [ ] Design conflict detection
- [ ] Create resolution strategies
- [ ] Implement attribute versioning
- [ ] Add notifications

**4.4.4. Add temporal weighting**
- [ ] Implement time decay functions
- [ ] Create recency boost
- [ ] Develop preference history tracking
- [ ] Add visualization

*Dependencies: 4.4.x depends on recommendation engine (4.3.x)*

### 5.3. Recommendation Endpoints

**5.3.1. Create POST /api/v1/recommendations endpoint**
- [ ] Implement route handler
- [ ] Create schema and validation
- [ ] Add rate limiting
- [ ] Implement error handling

**5.3.2. Implement request validation**
- [ ] Create validation schema
- [ ] Implement validation logic
- [ ] Add input sanitization
- [ ] Create error messages

**5.3.3. Connect to agent recommendation workflow**
- [ ] Integrate with LangGraph
- [ ] Implement async processing
- [ ] Add timeout handling
- [ ] Create status checking

**5.3.4. Format responses**
- [ ] Design response schema
- [ ] Implement serialization
- [ ] Add pagination
- [ ] Create multiple formats

*Dependencies: 5.3.x depends on recommendation engine (4.3.x)*

## Phase 4: Additional Data Sources

### 3.2. Calendar Integration

**3.2.1. Implement Google Calendar OAuth flow**
- [ ] Set up API credentials
- [ ] Create consent screen
- [ ] Implement authorization
- [ ] Create token handling
- [ ] Define error handling strategy for ingestion pipelines (e.g., retries, logging, DLQ).

**3.2.2. Create data fetcher for calendar events**
- [ ] Implement API client
- [ ] Create pagination handling
- [ ] Implement circuit breakers or robust error handling for external API calls
- [ ] Implement incremental sync

**3.2.3. Develop parser for calendar data**
- [ ] Create event parser
- [ ] Implement recurrence handling
- [ ] Add location extraction
- [ ] Create entity recognition

**3.2.4. Create Mem0 and Graphiti ingestion pipelines**
- [ ] Develop transformers
- [ ] Implement event-to-memory conversion
- [ ] Create relationship extraction
- [ ] Add pattern detection

*Dependencies: 3.2.x can be done after Phase 1*

### 3.3. Social Media Integration

**3.3.1. Fetch scraped data from Twitter**
- [ ] There is an api service at `https://twitter-scraper-finetune.onrender.com` that we can use, just need to send it the handle
- [ ] Poll the job at `https://twitter-scraper-finetune.onrender.com/twitter_scrape_jobs/{ID}/status` until it is done, then download the results (zip file of tweets in json)

**3.3.2; Develop tweet parser/analyzer**
- [ ] Create content extraction
- [ ] Implement sentiment analysis
- [ ] Add topic classification
- [ ] Create entity extraction

**3.3.3. Create Mem0 and Graphiti ingestion pipelines**
- [ ] Develop transformers
- [ ] Implement conversion
- [ ] Create relationship extraction
- [ ] Add interest detection

*Dependencies: 3.3.x can be done after Phase 1*

### 4.5. Trait Extraction Agent

**4.5.1. Develop targeted LLM prompts**
- [ ] Create prompt templates
- [ ] Implement specific prompts
- [ ] Add few-shot examples
- [ ] Create prompt chaining

**4.5.2. Implement confidence scoring**
- [ ] Design calculation algorithm
- [ ] Create validation rules
- [ ] Implement cross-reference checking
- [ ] Add thresholds

**4.5.3. Create UserProfile update logic**
- [ ] Implement update service
- [ ] Create merge strategies
- [ ] Add conflict resolution
- [ ] Implement batch processing

**4.5.4. Add Graphiti relationship creation**
- [ ] Develop trait-to-graph mapping
- [ ] Implement batch creation
- [ ] Add validation
- [ ] Create cleanup

*Dependencies: 4.5.x can be developed in parallel with 4.2.x, but integration depends on 4.2.x*

## Phase 5: Metrics & Evaluation

### 6.1. Trait Recall Accuracy

**6.1.1. Create a golden dataset**
- [ ] Identify key traits
- [ ] Create test cases
- [ ] Implement query variations
- [ ] Develop scoring criteria

**6.1.2. Develop a test harness**
- [ ] Create testing framework
- [ ] Implement query generation
- [ ] Add result evaluation
- [ ] Create reporting

**6.1.3. Implement accuracy scoring**
- [ ] Design scoring algorithm
- [ ] Create partial matching
- [ ] Implement adjusted scoring
- [ ] Add category metrics

**6.1.4. Create reporting dashboard**
- [ ] Design visualization
- [ ] Implement trend analysis
- [ ] Add drill-down
- [ ] Create exports

*Dependencies: 6.1.x depends on UserProfile implementation (1.2, 1.3)*

### 6.2. Recommendation Relevance Scoring

**6.2.1. Design user feedback collection**
- [ ] Create UI components
- [ ] Implement feedback types
- [ ] Add implicit tracking
- [ ] Develop A/B testing

**6.2.2. Implement relevance scoring algorithm**
- [ ] Design multi-dimensional scoring
- [ ] Create normalization
- [ ] Implement comparison
- [ ] Add confidence intervals

**6.2.3. Create historical tracking**
- [ ] Implement time-series storage
- [ ] Create aggregation
- [ ] Develop anomaly detection
- [ ] Add goal tracking

**6.2.4. Add visualization**
- [ ] Design dashboards
- [ ] Implement trend views
- [ ] Create quality comparison
- [ ] Add segment analysis

*Dependencies: 6.2.x depends on recommendation engine (4.3.x) and feedback mechanism (4.4.x)*

### 6.3. Source Diversity Metrics

**6.3.1. Create source tracking**
- [ ] Implement source metadata
- [ ] Create usage tracking
- [ ] Add attribution logging
- [ ] Develop categorization

**6.3.2. Develop diversity measurement**
- [ ] Design diversity metrics
- [ ] Implement balance calculation
- [ ] Create time-window analysis
- [ ] Add user-specific metrics

**6.3.3. Implement gap analysis**
- [ ] Create domain coverage mapping
- [ ] Implement source mapping
- [ ] Develop detection
- [ ] Add recommendations

**6.3.4. Build reporting interface**
- [ ] Design dashboard
- [ ] Implement visualization
- [ ] Create alerts
- [ ] Add improvement suggestions

*Dependencies: 6.3.x depends on data source implementations (3.x)*

### 6.4. Knowledge Gap Identification

**6.4.1. Implement topic coverage analysis**
- [ ] Create topic modeling
- [ ] Implement completeness scoring
- [ ] Add confidence assessment
- [ ] Develop temporal analysis

**6.4.2. Develop confidence scoring**
- [ ] Design domain metrics
- [ ] Implement uncertainty quantification
- [ ] Create confidence visualization
- [ ] Add trend analysis

**6.4.3. Create prompts for targeted questions**
- [ ] Design question templates
- [ ] Implement prioritization
- [ ] Add conversational strategies
- [ ] Create feedback loop

**6.4.4. Build UI for knowledge gaps**
- [ ] Design interface
- [ ] Implement gap filling
- [ ] Create gamification
- [ ] Add progress tracking

*Dependencies: 6.4.x depends on 6.1.x, 6.2.x, and 6.3.x*

## Critical Path Summary

The critical path for this migration is:

1. **Database Schema Changes** (1.x) → 
2. **Agent Profile Integration** (4.2.x) → 
3. **Recommendation Engine** (4.3.x) → 
4. **Feedback Mechanisms** (4.4.x) → 
5. **Recommendation Endpoints** (5.3.x) → 
6. **Recommendation Metrics** (6.2.x)

This path ensures we build the most essential functionality first (personalized recommendations) while allowing for parallel work on non-blocking tasks like additional data sources and advanced features. 