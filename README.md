# Digital Twin & DAO Coordination Backend

This project builds a Python backend that:
1. **Creates per‑member digital twins** with persistent memory in **Mem0**
2. **Maintains a shared temporal knowledge graph** (policies, proposals, votes) in **Graphiti** with **Neo4j** as the backend
3. Exposes REST / SSE endpoints for a Next.js frontend to consume

## Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [VS Code](https://code.visualstudio.com/) with [Remote Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- Python 3.12

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
   pip install -e ".[dev]"
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

- `POST /upload` - Upload and ingest files
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

## Features

- Memory management with Mem0
- Knowledge graph integration with Graphiti/Neo4j
- Entity extraction and relationship discovery
- Automated document processing and chunking
- File upload API with validation and deduplication
- Intelligent chunking with document structure awareness
- Metadata extraction from document content
- Asynchronous processing with Celery

## Ingestion Pipeline

The system processes documents through a sophisticated pipeline:

1. **File Upload**: Documents are uploaded and basic validation is performed
2. **Content Parsing**: Files are parsed based on type (PDF, MD, TXT)
3. **Entity Extraction**: spaCy extracts entities like people, organizations, locations
4. **Smart Chunking**: Content is split into semantic chunks while respecting document structure
5. **Mem0 Storage**: Chunks are stored in Mem0 with metadata and deduplication
6. **Graphiti Integration**: Entities and relationships are registered in the knowledge graph

### Entity Extraction

The system uses spaCy to identify entities such as:
- People (PERSON)
- Organizations (ORG)
- Locations (GPE, LOC)
- Products
- Dates and Times
- Events
- And more

Relationships between entities appearing in the same context are also inferred and stored in the knowledge graph.

## Getting Started

### Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Download spaCy models: `python app/scripts/download_models.py`
4. Configure environment variables (see `.env.example`)
5. Start services: `docker-compose up -d`
6. Run migrations: `alembic upgrade head`
7. Start the API: `uvicorn app.main:app --reload`
