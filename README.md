# Digital Twin with Coordination Backend

This project builds a Python backend that:
1. **Creates per‑member digital twins** with persistent memory in **Mem0**
2. **Maintains a shared temporal knowledge graph** (policies, proposals, votes) in **Graphiti** with **Neo4j** as the backend
3. Uses **LangGraph** to orchestrate multi-agent coordination
4. Exposes REST / SSE endpoints for a Next.js frontend to consume

The main user story:
- User - upload docs, tweets, and other sources	-> my twin learns my preferences
- User - chat with my twin -> refine its memory & get advice, recommendations, answers
- Twin agent - read from memories and graph -> make recommendations and chat with memory

See design docs in the `dev_docs` folder:
- [`v0_v1_strategy_shift.md`](./dev_docs/v0_v1_strategy_shift.md) for new PRD
- [`v1_tasks.md`](./dev_docs/v0-tasks-backend.md) for task list
- [`v1_architecture.md`](./dev_docs/v1_architecture.md) for desired architecture
- [`v1_api.md`](./dev_docs/v1_api.md) for current api
- Graphiti:
   - [`CONTENT_SCOPING.md`](./dev_decs/CONTENT_SCOPING.md) for how graphs are scoped to user, twin, or global
   - [`graphiti_filtering.md`](./dev_docs/graphiti_filtering.md) for how we filter and refine NER entities for graphiti
- LangGraph:
   - [`langgraph_workflow.md`](./dev_docs/langgraph_workflow.md) for how the basic langgraph agent works


## Setup

### Prerequisites

- Python 3.12
- [Docker](https://docs.docker.com/get-docker/) - optional
- [Docker Compose](https://docs.docker.com/compose/install/) - optional
- [VS Code](https://code.visualstudio.com/) with [Remote Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) - optional

### Local Development

1. Clone the repository
   ```
   git clone https://github.com/yourusername/digital-twin-dao.git
   cd digital-twin-dao
   ```

2. Copy the example environment file
   ```
   cp .env.example .env
   ```

3. There are two ways to develop:

   **Option A: Using VS Code Dev Container**
   ```
   code .
   ```
   Then click "Reopen in Container" when prompted or use Command Palette (F1) and select "Remote-Containers: Reopen in Container"

   **Option B: Local Python Development**
   ```
   # Create and activate virtual environment
   python3.12 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows

   # Install dependencies
   pip install -r requirements.txt
   ```

4. Start the required services (if not using dev container)
   ```
   docker-compose up -d db redis neo4j
   ```

5. Set up the project and start the development server
   ```
   make setup
   make dev
   ```

### Additional Configuration

#### Gemini API (Optional)

To use the Gemini-based entity extraction:

1. Get a Google Gemini API key from [AI Studio](https://aistudio.google.com/)
2. Add it to your `.env` file:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
3. Tune whether to use ENABLE_PROFILE_UPDATES (to extract traits into UserProfile model in Postgres), and/or ENABLE_GRAPHITI_INGESTION (to extract entities, relationships, traits into Graphiti)
   ```
   ENABLE_PROFILE_UPDATES=false
   ENABLE_GRAPHITI_INGESTION=true
   ```

We default to ENABLE_GRAPHITI_INGESTION=true and ENABLE_PROFILE_UPDATES=false since we already ingesting traits into Graphiti as relationships (which allow for search), so no need for UserProfile.

## Running the Backend

1. Start the required services (if not already running)
   ```
   docker-compose up -d db redis neo4j
   ```

2. Start the API server
   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. Start the Celery worker for background tasks
   ```
   export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
   celery -A app.worker worker -l info
   ```

4. Process a single file (for testing)
   ```
   python -m app.scripts.ingest_one_file "path/to/file.md"
   ```

   Or run this script to upload all files in `data` directory, in a Celery worker:
   ```
   python app/scripts/ingest_data_dir.py
   ```

5. Clear data for testing (optional)
   ```
   # Clear all data from both Mem0 and Graphiti
   python -m app.scripts.clear_data --all

   # Clear data for a specific user
   python -m app.scripts.clear_data --user-id user123

   # Clear only Mem0 data
   python -m app.scripts.clear_data --all --mem0

   # Clear Graphiti data with a specific scope
   python -m app.scripts.clear_data --user-id user123 --graphiti --scope user

   # Clear and rebuild Graphiti indexes (use whenever you add a new index or new property to an index in GraphitiService)
   python app/scripts/clear_data.py --all --rebuild-indexes 
   ```

6. Test the LangGraph agent with queries

There is a basic frontend to chat with your twin, to view your knowledgebase (mem0 memories and Graphiti entities and relations), and User Profile traits:
- Knowledge Base is only populated if ENABLE_GRAPHITI_INGESTION is true
- User Profile traits are only populated if ENABLE_PROFILE_UPDATES is true

To see it at `localhost:8001`
```
// Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

// Start celery worker
celery -A app.worker worker --loglevel=info
```

**IMPORTANT NOTES / KNOWN ISUES**:
- There is no auth yet, just a dummy user - you can control its DEFAULT_USER_ID in [`constants.py`](./app/core/constants.py)
- There are a LOT of server logs at startup, this is Neo4j vomiting out info about how the index already exists every time the server starts up, you can ignore those or comment out the `initialize_graph` call in [`startup_db_client`](./app/main.py) after the first db setup
- There are a lot of dev logs in general, these are still on for debugging
- Ingestion is suuuper slow right now because it has to ingest into mem0 (embeddings), then call into Gemini twice for entities/traits and relations, then create those entities/nodes and relations in Graphiti
- Retrieval is also super slow, still debugging this
   - mem0's call and graphiti's search call (if we comment out node_search) are both quick, about 0.1 and 0.2 seconds
   - BUT the response from openai takes 1.30 seconds!


## Useful API Commands

See the api's [README](./app/README.md) for full list of available endpoints. A sample:

### File Upload
```bash
# Upload a single file
curl -X POST http://localhost:8000/api/v1/upload
  -F "file=@path/to/file.md" \
  -F "async_processing=true"

# Process a directory
curl -X POST http://localhost:8000/api/v1/upload/process-directory
  -F "directory=documents"

# Check status of an async task
curl -X GET http://localhost:8000/api/v1/upload/task/{task_id} 
```

### Search
```bash
# General search (searches both memory and graph by default)
curl -X GET "http://localhost:8000/api/v1/search?query=your%20search%20query" 

# Memory-only search
curl -X GET "http://localhost:8000/api/v1/search?query=your%20search%20query&search_type=memory"

# Graph-only search
curl -X GET "http://localhost:8000/api/v1/search?query=your%20search%20query&search_type=graph"

# List ingested documents
curl -X GET "http://localhost:8000/api/v1/search/ingested-documents" 
```

### Chat API
```bash
# Chat with your digital twin
curl -X POST \
  "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you tell me about digital twins?"}'

# Chat with a specific user's digital twin
curl -X POST \
  "http://localhost:8000/api/v1/chat?user_id=specific-user" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What file formats are supported?"}'
```

## Project Structure

```
app/
├── api/            # API endpoints
├── core/           # Core application components
├── db/             # Database models and migrations
├── services/       # Business logic services
│   ├── memory/     # Mem0 integration
│   ├── graph/      # Graphiti integration
│   ├── ingestion/  # File/content ingestion
│   └── twin/       # Digital twin agent
├── worker/         # Celery tasks
└── main.py         # Application entry point
```

## Commands

- `make help` - Show available commands
- `make setup` - Install dependencies
- `make dev` - Run development server
- `make test` - Run tests
- `make lint` - Run linters
- `make format` - Format code
- `make migrate` - Run database migrations

## Technologies

- FastAPI & Uvicorn
- SQLAlchemy & Alembic
- Celery & Redis
- OpenAI & LangGraph
- Mem0 (vector memory)
- Graphiti (temporal knowledge graph) with Neo4j backend
- Entity extraction via Google Gemini

## Features

- Memory management with Mem0
- Knowledge graph integration with Graphiti/Neo4j, this extracts via Gemini:
   - entities like those in ENTITY_TYPE_MAPPING
   - relationship types like those in RELATIONSHIP_TYPES
   - trait relationships like TRAIT_TYPE_TO_RELATIONSHIP_MAPPING
- Automated document processing and chunking
- File upload API with validation and deduplication
- Intelligent chunking with document structure awareness
- Metadata extraction from document content
- Chat message ingestion
- Auto-summarize every 20 chat messages (see SummarizationService) and store:
   - Conversation models with latest summary (augmented with newest 20 messages) in Postges
   - Summaries of every 20 chat chunks in mem0
- Asynchronous processing with Celery on ingestion and summarization
- Optimized database queries for Neo4j, with full text search queries via GraphitiService
- UI that includes:
   - Chat with your twin
   - View Knowledge Base - mem0 memories and graphiti entities and relations

## How this Works (as of 2025-04-26)

High-level overview:
1. **Upload**: you can upload a file through api endpoint, or add messages through the frontend UI by chatting with your twin.
2. **Ingestion**: We then *ingest* the file or chat message through [`extraction_pipeline.py`](./app/services/extraction_pipeline.py), which for each text chunk and chat message:
   - Store them in mem0, with a ttl based on manual importance_scores (see `SyncChatMem0Ingestion.py`) - mem0 does embeddings itself, and handles conflicts and updates
   - Use Gemini to extract entities (including traits like a skill, interest, preference etc), extract relationships beween those entities (see [constants.py](./app/services/common/constants.py))
   - Store those extracted entities, traits, and relationships into Graphiti as a knowledge graph
3. **Retrieval**: When you chat with your twin, it hits the `/chat` endpoint which uses a RAG approach (see [`graph_agent.py`](./app/services/agent/graph_agent.py)):
   - `_retrieve_from_mem0` - retrieve memories from mem0
   - `_retrieve_from_graphiti` - retrieve top 5 related entities and top 5 graph search facts from Graphiti
   - `_merge_context` - calls into OpenAI with the merged prompt
4. **Summarize**: 
   - For chats only, we also store them as `Conversation` models in postgres, which hold many chat messages. Every 20 messages, we queue a summarization task, which updates the Conversation model with the latest summary, and stores that summarized chunk of 20 messages into mem0 for long-term safekeeping.
   - During chat/retrieval, we fetch the latest summary from the current conversation and the two others from before that in other conversations, as further context.

**Defunct components**:
1. We also have a [UserProfile](./app/db/models/user_profile.py) model that has attributes, skills, preferences, traits etc. This has been deprecated to using Graphiti relations instead, since those are more semantically queryable unlike postgres. Many of these are embedded in memories as well.
2. We have a related [TraitExtractionService](./app/services/traits/service.py) that we used when we were separately extracting out traits and setting them on the UserProfile instead of Graphiti. This is now defunct, as Gemini's [`EntityExtractor`](./app/services/ingestion/entity_extraction_gemini.py) now handles traits and their connections to the user itself and processes them in Graphiti.


### Ingestion Pipeline

The system processes documents and chat messages through a sophisticated pipeline:

Documents:
1. **File Upload**: Documents are uploaded and basic validation is performed
2. **Content Parsing**: Files are parsed based on type (PDF, MD, TXT)
3. **Entity Extraction**: Using Gemini to extract entities like people, organizations, locations
4. **Smart Chunking**: Content is split into semantic chunks while respecting document structure
5. **Mem0 Storage**: Chunks are stored in Mem0 with metadata and deduplication
6. **Graphiti Integration**: Entities, relationships, and traits are registered in the knowledge graph

To quickly test the ingestion pipeline:

```bash
# Process a sample file in `data` directory
python -m app.scripts.ingest_one_file "4. My Year in Books 2020.md"

# Upload a file via api, read logs in Celery worker
curl -X POST \
  http://localhost:8001/api/v1/upload \
  -F "file=@data/Frontier Tower.md" \
  -F "async_processing=true"
```
