# Migration Plan from V0 to V1

See: `v0-instructions-backend.md` (initial PRD)

We want to pivot from the DAO multi-agent part of our PRD and focus entirely on creating the best, most representative digital twin possible, who will be available to chat with in an api. We already have personal documents ingested and `search` endpoints. However, we don't have full chat functionality yet (no chat logs are ingested or stored), and we don't have any sources of data outside the personal docs. You can see the current directory state in `v0_project_structure.md` and the completed tasks in `v0-tasks-backend.md`.

We need a Digital Twin that is able to:
1. Answer questions from the user about anything in the global context and in their own memory
2. Make recommendations on the project that the user is part of (this context will come from an external service), engage in chat with the user, and integrate the user's choice into memory
3. Coordinate with other agents on behalf of the user, representing them as faithfully as possible

Example proposals/questions that the twin will make recommendations on will look like:
- (app design decision) what kinds of fields should be in a user's profile on a dating site? (twin must know my design preferences, project goals)
- what would be the best day to host a barbecue at my house, and what should be on the menu? (twin must know my preferences for hosting, my schedule, other people's schedules etc)
- where should we go on vacation next month? (twin must represent my personal preferences and schedule)
- how should we split up this project's tasks between members of our team? (twins must know my skillsets, role, likes, time availability)

So the twin must be able to understand the user's biographical info, including things like:
- memories (retrieved from ingested chunks)
- relationships
- preferences
- dislikes and dealbreakers
- interests
- skillsets
- lifestyle
- schedule

So we will need a LOT of sources of data beyond personal docs, and we'll focus next on ingesting chats in particular. Here's the migration plan:

**Overall Strategy Shift:**

*   **De-prioritize/Remove DAO:** Eliminate components specifically for DAO coordination (Proposal/Vote models). There shouldn't be any DAO manager logic, related API endpoints or related endpoints yet and we can keep using the LangGraph agent (`graph_agent.py`) so no need to delete it.
*   **Deep User Modeling:** Focus all efforts on capturing, representing, and utilizing nuanced user information (preferences, skills, relationships, etc.).
*   **Contextual Recommendation Engine:** The primary output of the twin should be its ability to make highly personalized recommendations given external context, leveraging its deep user model.

**1. Data Ingestion Enhancements:**

*   **Expand Data Sources:** This is crucial for a representative twin. Prioritize based on richness and accessibility:
    *   **Essential:**
        *   **Chat Logs (Twin <> User):** *Must* be ingested back into Mem0 (and potentially Graphiti for key facts/preferences expressed). Tag this source distinctly. Use the existing chat endpoint logic but ensure persistence and feedback loop.
        *   **Calendar Data (Google Calendar):** Provides routine, availability, events, attendees (relationships). Requires OAuth flow. Use Google Calendar API. Extract event types, recurrence, attendees, locations.
    *   **High Value:**
        *   **Social Media (Twitter/X):** Captures public persona, interests, opinions, network. Requires Twitter API access (can be complex/costly). Extract topics, sentiment, user interactions.
        *   **Professional Networks (LinkedIn):** Excellent for skills, work history, connections. API access is restricted; might require scraping (fragile) or user-uploaded profile data.
        *   **Other Chat Logs (Discord/Slack/Telegram):** Rich conversational data reflecting communication style, interests, relationships within specific communities. Requires API access or user exports. Parse messages, identify user interactions, extract topics.
    *   **Valuable:**
        *   **Personal Website/Blog:** Scrape for user's own writing, projects, interests. Use basic web scraping libraries (like `BeautifulSoup`, `httpx`).
        *   **Code Repositories (GitHub/GitLab):** Analyze commit messages, languages used, project descriptions to infer technical skills and interests. Requires API access/OAuth.
    *   **Consider (Privacy Sensitive):**
        *   **Email (IMAP):** Very rich but high privacy barrier. Requires user consent and careful handling. Could extract communication patterns, topics, relationships.
        *   **Streaming History (Spotify/Netflix):** Indicates interests and preferences. Requires API access/OAuth.
*   **Source-Specific Extractors:** Develop dedicated parsing and extraction logic for each new source type. Don't just dump raw text. Extract structured information where possible (e.g., meeting attendees from calendar, skills from LinkedIn, languages from GitHub).
*   **Metadata Tagging:** Rigorously tag all ingested data in Mem0/Graphiti with its `source_type` (e.g., 'document', 'chat_twin', 'calendar', 'twitter'), `original_id` (e.g., tweet ID, event ID), `timestamp`, and potentially confidence scores for extracted information.
*   **Continuous/Periodic Ingestion:** Implement background tasks (Celery) to periodically sync dynamic sources like calendars or social media feeds.

**2. Data Representation & Schema Changes:**

*   **Deprecate DAO Models:** Remove `app/db/models/proposal.py` and `app/db/models/vote.py`. Update Alembic migrations accordingly.
*   **Introduce `UserProfile` Model:** Create a dedicated `UserProfile` table/model linked one-to-one with the `User` model. This avoids bloating the `User` model and provides a structured place for distilled traits.
    ```python
    # Example: app/db/models/user_profile.py
    from sqlalchemy import Column, String, JSON, ForeignKey
    from sqlalchemy.orm import relationship, Mapped, mapped_column
    from app.db.base_class import Base

    class UserProfile(Base):
        id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), primary_key=True)
        user: Mapped["User"] = relationship(back_populates="profile")

        # Store structured, extracted traits
        attributes: Mapped[dict] = mapped_column(JSON, default=dict) # e.g., {"has a husband named Kyle", "has two kyles", "grew up in the Midwest"}
        preferences: Mapped[dict] = mapped_column(JSON, default=dict) # e.g., {"food": ["spicy", "vegetarian"], "travel": "budget"}
        interests: Mapped[list] = mapped_column(JSON, default=list)   # e.g., ["AI", "hiking", "jazz music"]
        skills: Mapped[list] = mapped_column(JSON, default=list)     # e.g., ["Python", "Project Management", "Data Analysis"]
        dislikes: Mapped[list] = mapped_column(JSON, default=list)   # e.g., ["early mornings", "public speaking"]
        communication_style: Mapped[dict] = mapped_column(JSON, default=dict) # e.g., {"formality": "informal", "sentiment": "positive"}
        key_relationships: Mapped[list] = mapped_column(JSON, default=list) # e.g., [{"person_name": "Jane Doe", "relationship": "colleague", "context": "Project X"}]

        # Add other relevant extracted fields
    ```
    *   Update `app/db/models/user.py` to include `profile: Mapped["UserProfile"] = relationship(back_populates="user", cascade="all, delete-orphan")`.
*   **Refine Graphiti Schema:**
    *   Explicitly model `Skill`, `Interest`, `Preference`, `Dislike` as node types.
    *   Create relationships like `(:User)-[:HAS_SKILL]->(:Skill)`, `(:User)-[:INTERESTED_IN]->(:Interest)`, `(:User)-[:PREFERS]->(:Preference)`, which could look like:

```
   (:User)-[:HAS_ATTRIBUTE {attribute}]->(:Attribute {name})
   (:User)-[:HAS_SKILL {proficiency}]->(:Skill {name})
   (:User)-[:INTERESTED_IN {level}]->(:Interest {name})
   (:User)-[:PREFERS {strength}]->(:Preference {category, value})
   (:User)-[:DISLIKES {strength}]->(:Topic {name})
   (:User)-[:KNOWS {relationship_type, strength}]->(:Person {name})
   (:User)-[:AVAILABILITY {recurrence}]->(:TimeSlot {day, time})
```

    *   Focus `Person` relationships: Model `(:User)-[:KNOWS {context, strength}]->(:Person)` or similar, derived from calendar, chats, etc. Store context (e.g., "colleague on Project X", "met at Conference Y").
    *   Ensure `Document`, `ChatMessage`, `Event` nodes are linked back to the `(:User)` who owns/created them or was involved. Use the `scope` and `owner_id` properties effectively.
*   **Mem0 Strategy:** Continue using Mem0 for storing text chunks (documents, chats) enabling semantic search. Enrich metadata significantly (source, timestamp, keywords, extracted entities, associated user profile traits):
    * Add `confidence_score`, `context`, `extraction_method`
    * Add `last_confirmed_date` for tracking when traits were last validated


**3. Agent Architecture & Enhancement:**

*   **Refine LangGraph Agent:**
    *   **Profile Integration:** Add a dedicated node in the LangGraph workflow to fetch the structured `UserProfile` data.
    *   **Enhanced Context Synthesis:** Modify the `merge_context` node to intelligently combine:
        *   Structured data from `UserProfile`.
        *   Relevant semantic memories from Mem0 search.
        *   Relevant structured facts/relationships from Graphiti search.
        *   Prioritize profile data and recent memories.
    *   **Recommendation Engine Node:** Create a new node specifically for generating recommendations. Its prompt should explicitly instruct the LLM to:
        *   Use the provided user profile (preferences, skills, dislikes, etc.).
        *   Consider the retrieved memories and graph facts.
        *   Analyze the `external_context` (the project description/question).
        *   Generate recommendations *justifying* them based on the user's traits. They should also include source attributions at the bottom.
        *   If there isn't enough info, the twin should ask the user questions (and process/ingest those to mem0 and graphiti, update the UserProfile if relevant etc in a background task) until it collects enough data to generate the recommendation.
    *   **Feedback Loop:** Add a mechanism (potentially another agent node or API endpoint) to receive user feedback on recommendations (e.g., "good recommendation", "doesn't match my preference"). Use this feedback to update the `UserProfile` and add corrective memories to Mem0.
    *   **Chat feedback loop**: Ensure that chat logs and any other ingested sources should also be updating the `UserProfile`, Mem0, and graphiti if they contain relevant updates.
*   **Trait Extraction Agent (Optional but Recommended):** Consider a separate agent task (or part of the ingestion pipeline) that specifically runs over ingested text (chats, documents) *solely* to extract and update the structured `UserProfile` data (preferences, skills, etc.). This could use more targeted LLM prompts than general entity extraction.
    * Add conflict resolution logic when contradictory information appears across sources
    * Implement confidence scoring for extracted traits (e.g., "90% confident user dislikes early meetings")
    * Use temporal weighting (more recent preferences may override older ones)

**4. API Endpoint Changes:**

*   **Remove DAO Endpoints:** Delete `/proposals/*` if it exists.
*   **Enhance Twin Profile Endpoint:**
    *   `GET /api/v1/twins/{uid}/profile` (or `/api/v1/profile` if always acting as self): Return the structured `UserProfile` data along with maybe some Mem0/Graphiti stats. 
    *   `PUT /api/v1/twins/{uid}/profile` (or `/api/v1/profile`): Allow the user to directly view and *correct/update* their structured profile traits. This is vital for accuracy and user trust.
*   **Add Recommendation Endpoint:**
    *   `POST /api/v1/twins/{uid}/recommendations` (or `/api/v1/recommendations`):
        *   Request Body: `{ "external_context": "Description of the project/decision needed..." }`
        *   Response: `{ "recommendations": [ {"recommendation": "...", "justification": "Based on your preference for X and skill Y...", "confidence": 0.85}, ... ] }`
*   **Enhance Chat Endpoint:**
    *   `POST /api/v1/chat`: Ensure chat history (user message + twin response) is logged to the database (`ChatMessage`) and *fed back into Mem0* with appropriate metadata (e.g., `source: chat_twin`).
*   **Add Ingestion Source Management (Future):**
    *   `GET /api/v1/ingestion_sources`: List currently connected data sources for the user.
    *   `POST /api/v1/ingestion_sources`: Initiate connection flow for new sources (e.g., start OAuth for Google Calendar).
    *   `DELETE /api/v1/ingestion_sources/{source_id}`: Disconnect a data source.

**5. Configuration & Tooling:**

*   Update `.env.example` and `config.py` to include API keys/settings for new data sources (Calendar, Twitter, etc.).
*   Add necessary SDKs/libraries for new data sources to `requirements.txt`.
*   Enhance utility scripts (`clear_data.py`, `ingest_data_dir.py`) to handle the refined schema and profile data if necessary.

**6. Add evaluation metrics:**

We need metrics for:
- Trait recall accuracy (testing twin against known user traits)
- Recommendation relevance scoring
- Source diversity metrics (ensuring twin uses multiple sources)
- Identify where are the biggest knowledge gaps - we can have the twin directly ask the user in a chat, or have those listed on the user profile page for the user to fill in.

**Summary of Key Changes:**

1.  **Remove DAO:** Prune models, APIs, logic related to proposals and voting.
2.  **Add UserProfile:** Create a structured store for distilled user traits.
3.  **Expand Ingestion:** Integrate Calendar, Chats (Twin & External), Social Media, etc.
4.  **Refine Graph:** Model Attributes, Skills, Interests, Preferences explicitly; focus Person relationships.
5.  **Enhance Agent:** Integrate Profile data, create dedicated Recommendation node, implement feedback loop.
6.  **Update APIs:** Add Profile and Recommendation endpoints, remove DAO ones, ensure chat feedback.

