# Digital Twin & DAO API

This README provides instructions for running and using the Digital Twin & DAO API.

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