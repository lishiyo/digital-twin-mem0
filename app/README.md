# Digital Twin API

This README provides instructions for running and using the Digital Twin API.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables (see .env.example)

3. Run PostgreSQL and Redis:
   ```bash
   docker-compose up -d db redis
   ```

4. Apply database migrations:
   ```bash
   alembic upgrade head
   ```

## Running the API

Start the API server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Running the Celery Worker

Start the Celery worker for background tasks:

```bash
celery -A app.worker worker -l info
```

## Performance and Cost Optimization

Mem0 and Graphiti can generate significant OpenAI API costs due to their extensive use of embeddings and completion calls. The following optimizations have been made:

1. **Disabled Inference**: By default, LLM inference in Mem0 is disabled, which significantly reduces API calls
2. **Configurable Processing**: All memory services accept an `infer` parameter to control whether advanced processing is enabled

If you need to enable inference for specific use cases, you can do so selectively:

```python
# For a single memory with inference enabled (more API calls but richer knowledge extraction)
result = await memory_service.add(content, user_id, metadata, infer=True)

# For batch processing with inference disabled (faster, cheaper)
result = await memory_service.add_batch(items, user_id, infer=False)
```

## API Endpoints

### File Upload API

The File Upload API allows you to upload files for ingestion into the digital twin's memory.

#### Single File Upload

```
POST /api/v1/upload
```

Parameters:
- `file`: The file to upload (multipart/form-data)
- `async_processing`: Boolean (default: true) - Whether to process the file asynchronously

Example using curl:
```bash
curl -X POST \
  http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/file.txt" \
  -F "async_processing=true"
```

Response:
```json
{
  "status": "accepted",
  "message": "File uploaded and queued for processing",
  "file_details": {
    "original_filename": "file.txt",
    "stored_filename": "a1b2c3d4e5f6.txt",
    "size": 1024,
    "hash": "abc123...",
    "content_type": "text/plain"
  },
  "task_id": "task-uuid",
  "user_id": "user-id"
}
```

#### Multiple File Upload

```
POST /api/v1/upload/batch
```

Parameters:
- `files`: List of files to upload (multipart/form-data)
- `async_processing`: Boolean (default: true) - Whether to process files asynchronously

Example using curl:
```bash
curl -X POST \
  http://localhost:8000/api/v1/upload/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@/path/to/file1.txt" \
  -F "files=@/path/to/file2.md" \
  -F "async_processing=true"
```

#### Check Task Status

```
GET /api/v1/upload/task/{task_id}
```

Parameters:
- `task_id`: The Celery task ID returned from an async upload

Example using curl:
```bash
curl -X GET \
  http://localhost:8000/api/v1/upload/task/task-uuid \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "status": "success",
  "message": "Task completed successfully",
  "result": { ... task result data ... }
}
```

#### Process Directory

```
POST /api/v1/upload/process-directory
```

Parameters:
- `directory`: Optional subdirectory to process (relative to data dir)
- `async_processing`: Boolean (default: true) - Whether to process the directory asynchronously

Example using curl:
```bash
curl -X POST \
  http://localhost:8000/api/v1/upload/process-directory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "directory=documents" \
  -F "async_processing=true"
```

## Supported File Types

Currently supported file types:
- `.txt` - Plain text files
- `.md` - Markdown files
- `.pdf` - PDF documents (requires additional dependencies)

## File Size Limits

- Maximum file size: 10MB per file
- Maximum batch size: No hard limit, but consider network limitations

## Security Features

The API includes several security features:
- Authorization required for all endpoints
- File type validation
- File size validation
- Basic content security scanning
- Unique filename generation to prevent overwriting

## Troubleshooting

Common issues:
1. **File upload fails with 415 error**: Check if the file type is supported
2. **File exceeds size limit**: Files must be under 10MB
3. **Celery task pending indefinitely**: Ensure Redis and Celery worker are running
4. **File safety check failed**: The file failed security validation (may contain suspicious content)

## Utility Scripts

### Data Cleanup

The system includes a utility script for clearing data during testing and development:

```bash
# Location: app/scripts/clear_data.py

# Clear all data from both Mem0 and Graphiti (will prompt for confirmation)
python -m app.scripts.clear_data --all

# Clear data for a specific user
python -m app.scripts.clear_data --user-id user123

# Clear only Mem0 data
python -m app.scripts.clear_data --all --mem0

# Clear only Graphiti data 
python -m app.scripts.clear_data --all --graphiti

# Clear Graphiti data with a specific scope
python -m app.scripts.clear_data --user-id user123 --graphiti --scope user

# Skip confirmation prompt (use with caution)
python -m app.scripts.clear_data --all --force
```

### File Ingestion

For testing file processing:

```bash
# Process a single file
python -m app.scripts.ingest_one_file path/to/file.md

# Default behavior: uses test-user ID and processes synchronously
```

## API Examples

### File Upload

```bash
# Upload a single file
curl -X POST \
  http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/file.txt" \
  -F "async_processing=true"

# Upload multiple files
curl -X POST \
  http://localhost:8000/api/v1/upload/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@/path/to/file1.txt" \
  -F "files=@/path/to/file2.md"

# Process a directory
curl -X POST \
  http://localhost:8000/api/v1/upload/process-directory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "directory=documents"
  
# Check task status
curl -X GET \
  http://localhost:8000/api/v1/upload/task/{task_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search Operations

```bash
# Unified search (searches both memory and graph)
curl -X GET \
  "http://localhost:8000/api/v1/search?query=your%20search%20query" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Memory-only search
curl -X GET \
  "http://localhost:8000/api/v1/search?query=your%20query&search_type=memory&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Graph-only search 
curl -X GET \
  "http://localhost:8000/api/v1/search?query=your%20query&search_type=graph&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Use mock results for testing without actual data
curl -X GET \
  "http://localhost:8000/api/v1/search?query=test&use_mock=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List all ingested documents
curl -X GET \
  "http://localhost:8000/api/v1/search/ingested-documents" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List documents with limit
curl -X GET \
  "http://localhost:8000/api/v1/search/ingested-documents?limit=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Chat API

The Chat API allows you to interact with the digital twin agent, which uses the ingested documents to provide informed responses.

```bash
# Chat with the digital twin
curl -X POST \
  "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you tell me about digital twins?"}'

# Chat with a specific model
curl -X POST \
  "http://localhost:8000/api/v1/chat?model_name=gpt-4" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "How does the ingestion pipeline work?"}'

# Use a specific user ID
curl -X POST \
  "http://localhost:8000/api/v1/chat?user_id=specific-user" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What file formats are supported?"}'
```

Response format:
```json
{
  "user_message": "What can you tell me about digital twins?",
  "twin_response": "A digital twin is a virtual representation...",
  "user_id": "user-id",
  "model_used": "gpt-3.5-turbo"
}
```

### Agent Architecture

The digital twin is implemented using LangGraph, a framework for building structured agents. The agent workflow:

1. Retrieves relevant information from Mem0 (vector database)
2. Retrieves information from Graphiti (knowledge graph)
3. Merges context from both sources
4. Generates a response using an LLM

This approach provides the twin with both semantic understanding (vector embeddings) and structured knowledge (graph relationships), allowing for more informed and accurate responses.

### Coming in Future Updates

Future API features will include:
- Streaming responses (Server-Sent Events)
- Conversation history and context management
- Twin personalization
- Voting intent detection
- DAO proposal creation and management

## API Examples

### File Upload

```bash
# Upload a single file
curl -X POST \
  http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/file.txt" \
  -F "async_processing=true"

# Upload multiple files
curl -X POST \
  http://localhost:8000/api/v1/upload/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@/path/to/file1.txt" \
  -F "files=@/path/to/file2.md"

# Process a directory
curl -X POST \
  http://localhost:8000/api/v1/upload/process-directory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "directory=documents"
  
# Check task status
curl -X GET \
  http://localhost:8000/api/v1/upload/task/{task_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search Operations

```bash
# Unified search (searches both memory and graph)
curl -X GET \
  "http://localhost:8000/api/v1/search?query=your%20search%20query" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Memory-only search
curl -X GET \
  "http://localhost:8000/api/v1/search?query=your%20query&search_type=memory&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Graph-only search 
curl -X GET \
  "http://localhost:8000/api/v1/search?query=your%20query&search_type=graph&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Use mock results for testing without actual data
curl -X GET \
  "http://localhost:8000/api/v1/search?query=test&use_mock=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List all ingested documents
curl -X GET \
  "http://localhost:8000/api/v1/search/ingested-documents" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List documents with limit
curl -X GET \
  "http://localhost:8000/api/v1/search/ingested-documents?limit=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Chat API

```bash
# Chat with the digital twin
curl -X POST \
  "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you tell me about digital twins?"}'

# Chat with a specific model
curl -X POST \
  "http://localhost:8000/api/v1/chat?model_name=gpt-4" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "How does the ingestion pipeline work?"}'

# Use a specific user ID
curl -X POST \
  "http://localhost:8000/api/v1/chat?user_id=specific-user" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What file formats are supported?"}'
```

Response format:
```json
{
  "user_message": "What can you tell me about digital twins?",
  "twin_response": "A digital twin is a virtual representation...",
  "user_id": "user-id",
  "model_used": "gpt-3.5-turbo"
}
```

### Testing Chat Ingestion

To test the chat ingestion implementation:

1. Basic Chat Flow:
- Use the chat endpoint to send a message: `POST /api/v1/chat`
- This creates a conversation and messages in the database
- Triggers background tasks to process the messages

2. Verify Conversation Storage:
- Check the list of conversations: `GET /api/v1/chat/conversations`
- View a specific conversation: `GET /api/v1/chat/conversations/{id}`

3. Verify Memory Ingestion:
- Check the Mem0 connection: `GET /api/v1/memory/check`
- Check the Mem0 status of a message by message id: `GET /api/v1/chat/messages/{id}/mem0-status`
- View memories by conversation: `GET /api/v1/memory/memory-by-conversation/{id}`
- View a specific memory: `GET /api/v1/memory/memory/{id}`
- Manually trigger processing: `GET /api/v1/memory/trigger-process-conversation/{id}`

 If you encounter any issues, you can inspect the server and celery logs to see what's happening in the background processing jobs.


### Agent Architecture

The digital twin is implemented using LangGraph, a framework for building structured agents. The agent workflow:

1. Retrieves relevant information from Mem0 (vector database)
2. Retrieves information from Graphiti (knowledge graph)
3. Merges context from both sources
4. Generates a response using an LLM

This approach provides the twin with both semantic understanding (vector embeddings) and structured knowledge (graph relationships), allowing for more informed and accurate responses.

### Coming in Future Updates

Future API features will include:
- Conversation history and context management
- Streaming responses
- Twin personalization
- Recommendations from twins