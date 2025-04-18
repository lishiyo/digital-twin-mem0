# Digital Twin with Coordination Backend

This project builds a Python backend that:
1. **Creates per‑member digital twins** with persistent memory in **Mem0**
2. **Maintains a shared temporal knowledge graph** (policies, proposals, votes) in **Graphiti** with **Neo4j** as the backend
3. Uses **LangGraph** to orchestrate multi-agent coordination
4. Exposes REST / SSE endpoints for a Next.js frontend to consume

The main user story:
- User - upload docs & tweets	-> my twin learns my preferences
- User - chat with my twin -> refine its memory & get advice, recommendations, answers
- Twin agent - read shared wiki & proposals -> recommend votes
- DAO admin - view resolution dashboard -> track consensus in real time

See design docs in the `dev_docs` folder:
- [`v0-instructions-backend.md`](./dev_docs/v0-instructions-backend.md) for initial PRD
- [`v0-tasks-backend.md`](./dev_docs/v0-tasks-backend.md) for task list
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
3. Set the entity extractor type:
   ```
   ENTITY_EXTRACTOR_TYPE=gemini
   ```
   (Valid options: "spacy" or "gemini", defaults to "gemini" if the API key is available)

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
   ```

6. Test the LangGraph agent with queries

   ```
   // Update this with questions that should have been ingested
   python app/scripts/test_agent.py
   ```

## Useful API Commands

See the api's [README](./app/README.md) for list of available endpoints. A sample:

### File Upload
```bash
# Upload a single file
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@path/to/file.md" \
  -F "async_processing=true"

# Process a directory
curl -X POST http://localhost:8000/api/v1/upload/process-directory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "directory=documents"

# Check status of an async task
curl -X GET http://localhost:8000/api/v1/upload/task/{task_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search
```bash
# General search (searches both memory and graph by default)
curl -X GET "http://localhost:8000/api/v1/search?query=your%20search%20query" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Memory-only search
curl -X GET "http://localhost:8000/api/v1/search?query=your%20search%20query&search_type=memory" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Graph-only search
curl -X GET "http://localhost:8000/api/v1/search?query=your%20search%20query&search_type=graph" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List ingested documents
curl -X GET "http://localhost:8000/api/v1/search/ingested-documents" \
  -H "Authorization: Bearer YOUR_TOKEN"
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

## API Endpoints

- `POST /api/v1/upload` - Upload and ingest a single file
- `POST /api/v1/upload/batch` - Upload and ingest multiple files
- `POST /api/v1/upload/process-directory` - Process all files in a directory
- `GET /api/v1/upload/task/{task_id}` - Check status of an upload task
- `GET /twin/{uid}/profile` - Get digital twin profile
- `POST /twin/{uid}/chat` - Chat with a digital twin
- `GET /proposals/open` - List open proposals
- `GET /proposals/{pid}/status` - Get proposal status

## Technologies

- FastAPI & Uvicorn
- SQLAlchemy & Alembic
- Celery & Redis
- OpenAI & LangGraph
- Mem0 (vector memory)
- Graphiti (temporal knowledge graph) with Neo4j backend
- Entity extraction options:
  - spaCy (traditional NLP)
  - Google Gemini (AI-powered)

## Features

- Memory management with Mem0
- Knowledge graph integration with Graphiti/Neo4j
- Flexible entity extraction with two options:
  - **spaCy** (traditional NLP approach):
    - Support for 18+ entity types (people, organizations, locations, etc.)
    - Smart handling of Markdown content
    - Extraction from formatted text (bold, italic)
    - Intelligent filtering of non-entity content
  - **Google Gemini** (LLM-based approach):
    - More accurate entity extraction
    - Better understanding of context
    - Enhanced relationship detection
    - Improved keyword extraction
- Automated document processing and chunking
- File upload API with validation and deduplication
- Intelligent chunking with document structure awareness
- Metadata extraction from document content
- Asynchronous processing with Celery
- Optimized database queries for Neo4j

## Ingestion Pipeline

The system processes documents through a sophisticated pipeline:

1. **File Upload**: Documents are uploaded and basic validation is performed
2. **Content Parsing**: Files are parsed based on type (PDF, MD, TXT)
3. **Entity Extraction**: Using either spaCy or Gemini to extract entities like people, organizations, locations
4. **Smart Chunking**: Content is split into semantic chunks while respecting document structure
5. **Mem0 Storage**: Chunks are stored in Mem0 with metadata and deduplication
6. **Graphiti Integration**: Entities and relationships are registered in the knowledge graph

To quickly test the ingestion pipeline:

```bash
# Process a sample file
python -m app.scripts.ingest_one_file

# Run the integration test
python -m app.tests.integration.test_ingestion
```

### Entity Extraction

The system supports two entity extraction methods:

#### 1. spaCy (Traditional NLP)
- Uses a rule-based and statistical approach
- Identifies common entity types like People, Organizations, Locations
- Efficient but may miss complex context-dependent entities

#### 2. Gemini (Google's LLM)
- Uses an AI-powered approach for more accurate extraction
- Better at understanding context and nuanced entities
- Provides more accurate relationships between entities
- Requires a Google Gemini API key

You can switch between extractors using the `ENTITY_EXTRACTOR_TYPE` environment variable.

To compare the entity extraction methods:

```bash
# Run comparison with sample text
python -m app.services.ingestion.compare_extractors

# Run with a specific file
python -m app.services.ingestion.compare_extractors --input path/to/file.txt

# Output in JSON format
python -m app.services.ingestion.compare_extractors --format json
```