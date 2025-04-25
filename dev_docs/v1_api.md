# Digital Twin API Reference

This document outlines the API endpoints for the Digital Twin v1 implementation, as well existing endpoints in v0. All endpoints are prefixed with `/api/v1`.

## Chat

### POST /api/v1/chat

Sends a message to the digital twin and receives a response. All conversations are stored for search/retrieval and profile learning. **Note**: This REST endpoint is for MVP, we will 
switch to a real-time websockets implementation later (see [v1_chat_implementation.md](./
v1_chat_implementation.md)).

**Request:**
```json
POST /api/v1/chat
{
  "message": "What can you tell me about digital twins?",
  "conversation_id": "optional-conversation-id",
  "metadata": {
    "client_id": "web",
    "session_id": "uuid"
  }
}
```

Parameters:
- `message`: The message text to send to the digital twin
- `conversation_id` (optional): Specific conversation ID to continue (creates new if absent)
- `metadata` (optional): JSON blob of metadata for the conversation, including context

**Response:**
```json
{
  "conversation_id": "conversation-uuid",
  "message": "A digital twin is a virtual representation...",
  "mem0_task_id": "task-uuid"
}
```

### GET /api/v1/chat/conversations

List conversations for the current user with pagination.

**Request:**
```
GET /api/v1/chat/conversations?limit=10&offset=0
```

Parameters:
- `limit`: Maximum number of conversations to return (default: 10)
- `offset`: Offset for pagination (default: 0)

**Response:**
```json
{
  "total": 25,
  "offset": 0,
  "limit": 10,
  "conversations": [
    {
      "id": "conversation-uuid",
      "title": "Discussion about digital twins",
      "created_at": "ISO-8601 timestamp",
      "updated_at": "ISO-8601 timestamp",
      "summary": "Talked about the concept of digital twins and their applications..."
    },
    // More conversations...
  ]
}
```

### GET /api/v1/chat/conversations/{conversation_id}

Get details for a specific conversation including all messages. The summary field is the latest summary, though not all messages may have been included yet.

**Request:**
```
GET /api/v1/chat/conversations/{conversation_id}
```

**Response:**
```json
{
  "id": "conversation-uuid",
  "title": "Discussion about digital twins",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "summary": "Talked about the concept of digital twins and their applications...",
  "metadata": {
    "client_id": "web",
    "session_id": "uuid"
  },
  "messages": [
    {
      "id": "message-uuid",
      "role": "user",
      "content": "What can you tell me about digital twins?",
      "created_at": "ISO-8601 timestamp",
      "is_stored_in_mem0": true,
      "importance_score": 0.75
    },
    {
      "id": "message-uuid",
      "role": "assistant",
      "content": "A digital twin is a virtual representation...",
      "created_at": "ISO-8601 timestamp",
      "is_stored_in_mem0": false,
      "importance_score": 0.0
    }
    // More messages...
  ]
}
```

### GET /api/v1/chat/messages/{message_id}

Get details for a specific chat message.

**Request:**
```
GET /api/v1/chat/messages/{message_id}
```

**Response:**
```json
{
  "id": "message-uuid",
  "conversation_id": "conversation-uuid",
  "role": "user",
  "content": "What can you tell me about digital twins?",
  "timestamp": "ISO-8601 timestamp",
  "metadata": {
    "client_id": "web",
    "session_id": "uuid",
  },
  "is_stored_in_mem0": true,
  "importance_score": 0.75
}
```

### GET /api/v1/chat/messages/{message_id}/mem0-status

Check the Mem0 ingestion status for a specific message.

**Request:**
```
GET /api/v1/chat/messages/{message_id}/mem0-status
```

**Response:**
```json
{
  "message_id": "message-uuid",
  "is_stored_in_mem0": true,
  "mem0_memory_id": "memory-uuid",
  "importance_score": 0.75,
  "processed": true,
  "created_at": "ISO-8601 timestamp"
}
```

### POST /api/v1/chat/conversations/{conversation_id}/summarize

Manually trigger summarization of a conversation.

**Request:**
```
POST /api/v1/chat/conversations/{conversation_id}/summarize
```

**Response:**
```json
{
  "status": "pending",
  "task_id": "task-uuid",
  "conversation_id": "conversation-uuid",
  "message": "Summarization queued successfully"
}
```

### POST /api/v1/chat/conversations/{conversation_id}/generate-title

Generate or update a title for a conversation.

**Request:**
```
POST /api/v1/chat/conversations/{conversation_id}/generate-title
```

**Response:**
```json
{
  "status": "success",
  "conversation_id": "conversation-uuid",
  "title": "Discussion about digital twins"
}
```

### GET /api/v1/chat/conversations/context

Get context from previous conversations for a new conversation.

**Request:**
```
GET /api/v1/chat/conversations/context?current_conversation_id=optional-conversation-id
```

Parameters:
- `current_conversation_id` (optional): Current conversation ID to exclude from context

**Response:**
```json
{
  "status": "success",
  "context": "Previous conversations summary text...",
  "has_context": true
}
```

## File Upload API (already in v0)

#### POST /api/v1/upload

Upload a single file for ingestion into the digital twin's memory.

**Request:**
```
POST /api/v1/upload
```

Parameters:
- `file`: The file to upload (multipart/form-data)
- `async_processing`: Boolean (default: true) - Whether to process the file asynchronously

**Response:**
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

#### POST /api/v1/upload/batch

Upload multiple files for ingestion.

**Request:**
```
POST /api/v1/upload/batch
```

Parameters:
- `files`: List of files to upload (multipart/form-data)
- `async_processing`: Boolean (default: true) - Whether to process files asynchronously

#### GET /api/v1/upload/task/{task_id}

Check the status of an asynchronous file processing task.

**Request:**
```
GET /api/v1/upload/task/{task_id}
```

Parameters:
- `task_id`: The Celery task ID returned from an async upload

**Response:**
```json
{
  "status": "success",
  "message": "Task completed successfully",
  "result": { ... task result data ... }
}
```

#### POST /api/v1/upload/process-directory

Process all files in a specified directory.

**Request:**
```
POST /api/v1/upload/process-directory
```

Parameters:
- `directory`: Optional subdirectory to process (relative to data dir)
- `async_processing`: Boolean (default: true) - Whether to process the directory asynchronously


## Search API (already in v0)

#### GET /api/v1/search

Search for information across memory and knowledge graph.

**Request:**
```
GET /api/v1/search?query=your%20search%20query
```

Parameters:
- `query`: The search query
- `search_type`: Type of search ("memory", "graph", or omit for unified search)
- `limit`: Maximum number of results (default varies by search type)
- `use_mock`: Boolean (default: false) - Whether to use mock results for testing

**Response:**
(Response format varies based on search type)

#### GET /api/v1/search/ingested-documents

List all documents that have been ingested into the system.

**Request:**
```
GET /api/v1/search/ingested-documents
```

Parameters:
- `limit`: Maximum number of documents to return 

## Memory API

### GET /api/v1/memory/check

Check connection to Mem0 service.

**Request:**
```
GET /api/v1/memory/check
```

**Response:**
```json
{
  "status": "connected",
  "message": "Successfully connected to Mem0"
}
```

### GET /api/v1/memory/list

List memories with pagination and optional search query.

**Request:**
```
GET /api/v1/memory/list?limit=10&offset=0&query=optional_search_query
```

Parameters:
- `limit`: Maximum number of memories to return (default: 10)
- `offset`: Offset for pagination (default: 0)
- `query` (optional): Search query to filter memories

**Response:**
```json
{
  "memories": [
    {
      "id": "memory-uuid",
      "memory": "Content of the memory...",
      "name": "Memory name/title",
      "metadata": {
        "source": "chat",
        "memory_type": "message",
        "conversation_id": "conversation-uuid"
      },
      // Additional fields provided by Mem0...
    },
    // More memories...
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

### GET /api/v1/memory/memory/{memory_id}

Get a specific memory by ID.

**Request:**
```
GET /api/v1/memory/memory/{memory_id}
```

**Response:**
```json
{
  "id": "memory-uuid",
  "memory": "Content of the memory...",
  "name": "Memory name/title",
  "metadata": {
    "source": "chat",
    "memory_type": "message",
    "conversation_id": "conversation-uuid"
  },
  // Additional fields provided by Mem0...
}
```

### DELETE /api/v1/memory/memory/{memory_id}

Delete a specific memory by ID.

**Request:**
```
DELETE /api/v1/memory/memory/{memory_id}
```

**Response:**
```json
{
  "status": "success",
  "message": "Memory memory-uuid deleted successfully"
}
```

### GET /api/v1/memory/memory-by-conversation/{conversation_id}

Get memories stored in Mem0 for a specific conversation.

**Request:**
```
GET /api/v1/memory/memory-by-conversation/{conversation_id}?limit=20
```

Parameters:
- `limit`: Maximum number of memories to return (default: 20)

**Response:**
```json
{
  "conversation_id": "conversation-uuid",
  "total": 10,
  "memories": [
    // Array of memory objects...
  ]
}
```

### GET /api/v1/memory/trigger-process-conversation/{conversation_id}

Manually trigger processing for all messages in a conversation.

**Request:**
```
GET /api/v1/memory/trigger-process-conversation/{conversation_id}
```

**Response:**
```json
{
  "status": "processing",
  "conversation_id": "conversation-uuid",
  "task_id": "task-uuid",
  "message": "Processing has been triggered"
}
```

### GET /api/v1/memory/trigger-graphiti-process/{conversation_id}

Manually trigger Graphiti processing for all messages in a conversation.

**Request:**
```
GET /api/v1/memory/trigger-graphiti-process/{conversation_id}
```

**Response:**
```json
{
  "status": "processing",
  "conversation_id": "conversation-uuid",
  "task_id": "task-uuid",
  "message": "Graphiti processing has been triggered"
}
```

## Graph API

### GET /api/v1/graph/nodes

List graph nodes with pagination and optional filtering.

**Request:**
```
GET /api/v1/graph/nodes?limit=10&offset=0&query=optional_search_query&node_type=optional_node_type
```

Parameters:
- `limit`: Maximum number of nodes to return (default: 10)
- `offset`: Offset for pagination (default: 0)
- `query` (optional): Search query to filter nodes
- `node_type` (optional): Filter by node type (e.g., "Person", "Skill")

**Response:**
```json
{
  "nodes": [
    {
      "id": "node-uuid",
      "labels": ["Person"],
      "properties": {
        "name": "John Doe",
        "created_at": "ISO-8601 timestamp"
      }
    },
    // More nodes...
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

### GET /api/v1/graph/relationships

List graph relationships with pagination and optional filtering.

**Request:**
```
GET /api/v1/graph/relationships?limit=10&offset=0&query=optional_search_query&rel_type=optional_relationship_type&scope=user&owner_id=your_user_id
```

Parameters:
- `limit`: Maximum number of relationships to return (default: 10)
- `offset`: Offset for pagination (default: 0)
- `query` (optional): Search query to filter relationships
- `rel_type` (optional): Filter by relationship type (e.g., "KNOWS", "HAS_SKILL")
- `scope` (optional): Filter by scope ("user", "twin", "global"). Defaults to "user".
- `owner_id` (optional): Filter by owner ID. Defaults to current user ID if scope is "user".

**Response:**
```json
{
  "relationships": [
    {
      "id": "relationship-uuid",
      "type": "KNOWS",
      "start_node": "node-uuid-1",
      "end_node": "node-uuid-2",
      "properties": {
        "since": "2023-01-01",
        "confidence": 0.85
      }
    },
    // More relationships...
  ],
  "total": 15,
  "limit": 10,
  "offset": 0
}
```

### GET /api/v1/graph/node/{node_id}

Get a specific node by its ID.

**Request:**
```
GET /api/v1/graph/node/{node_id}
```

**Response:**
```json
{
  "id": "node-uuid",
  "labels": ["Person"],
  "properties": {
    "name": "John Doe",
    "created_at": "ISO-8601 timestamp"
  }
}
```

### DELETE /api/v1/graph/node/{node_id}

Delete a specific node by its ID.

**Request:**
```
DELETE /api/v1/graph/node/{node_id}
```

**Response:**
```json
{
  "status": "success",
  "message": "Node node-uuid deleted successfully"
}
```

### GET /api/v1/graph/relationship/{relationship_id}

Get a specific relationship by its ID.

**Request:**
```
GET /api/v1/graph/relationship/{relationship_id}
```

**Response:**
```json
{
  "id": "relationship-uuid",
  "type": "KNOWS",
  "start_node": "node-uuid-1",
  "end_node": "node-uuid-2",
  "properties": {
    "since": "2023-01-01",
    "confidence": 0.85
  }
}
```

### DELETE /api/v1/graph/relationship/{relationship_id}

Delete a specific relationship by its ID.

**Request:**
```
DELETE /api/v1/graph/relationship/{relationship_id}?logical=true
```

Parameters:
- `logical`: Perform logical delete (set valid_to) instead of physical delete (default: true)

**Response:**
```json
{
  "status": "success",
  "message": "Logically deleted relationship relationship-uuid"
}
```

## Health API

### GET /api/v1/health

Health check endpoint that verifies database connection.

**Request:**
```
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

## User Profile (Upcoming in V1)

###` GET /api/v1/profile`

Retrieves the current user's profile information including attributes, preferences, skills, interests, and relationships. The profile builds on extracted traits from all data sources (docs, chat logs, twitter, other data sources etc).

**Request:**
```
GET /api/v1/profile
```

**Response:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "preferences": {
    "theme": "dark",
    "notification_frequency": "daily",
    ...
  },
  "attributes": [
    {"name": "has two cats", "confidence": 0.9, "source": "chat_inference"},
    {"name": "has a husband named kyle", "confidence": 0.7, "source": "ingested_documents"},
    ...
  ],
  "interests": [
    {"name": "machine learning", "confidence": 0.9, "source": "chat_inference"},
    {"name": "hiking", "confidence": 0.7, "source": "user_input"},
    ...
  ],
  "skills": [
    {"name": "python", "proficiency": 0.8, "confidence": 0.95, "source": "chat_inference"},
    {"name": "public speaking", "proficiency": 0.7, "confidence": 0.6, "source": "calendar_inference"},
    ...
  ],
  "dislikes": [
    {"name": "early meetings", "confidence": 0.85, "source": "calendar_inference"},
    ...
  ],
  "communication_style": {
    "preferred_tone": "direct",
    "detailed_responses": true,
    ...
  },
  "key_relationships": [
    {"name": "Jane Doe", "relation": "colleague", "importance": 0.9, "source": "chat_inference"},
    ...
  ],
  "metadata": {
    "created_at": "ISO-8601 timestamp",
    "updated_at": "ISO-8601 timestamp",
    "confidence_scores": {
      "overall": 0.75,
      "interests": 0.8,
      "skills": 0.9,
      ...
    },
    "source_diversity": 0.65
  }
}
```

### `PUT /api/v1/profile`

Updates the user's profile information. Supports partial updates.

**Request:**
```json
{
  "preferences": {
    "theme": "light"
  },
  "interests": [
    {"name": "gardening", "confidence": 1.0, "source": "user_input"}
  ]
}
```

**Response:**
```json
{
  "id": "uuid",
  "updated_fields": ["preferences.theme", "interests"],
  "metadata": {
    "updated_at": "ISO-8601 timestamp"
  }
}
```


## Recommendations (Upcoming in V1)

### `POST /api/v1/recommendations`

Generates personalized recommendations based on the user's profile and provided context.

**Request:**
```json
{
  "recommendation_type": "activity",
  "context": {
    "location": "New York, NY",
    "weather": "rainy",
    "time_available": "2 hours",
    "current_mood": "relaxed"
  },
  "constraints": {
    "max_cost": 50,
    "accessibility_requirements": "wheelchair_accessible"
  },
  "preferences": {
    "prioritize": ["interests.art", "interests.technology"]
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "recommendations": [
    {
      "title": "Museum of Modern Art",
      "description": "Given your interest in art and the rainy weather, MoMA would be perfect for a 2-hour visit. They have wheelchair accessibility throughout.",
      "reasoning": "This matches your art interest (0.85 confidence), fits within your time constraint, and meets accessibility requirements. The indoor activity is ideal for rainy weather.",
      "confidence": 0.92,
      "metadata": {
        "cost": "$25",
        "location": "11 W 53rd St, New York, NY",
        "matches_traits": ["interests.art", "preferences.indoor_activities_on_rainy_days"]
      }
    },
    {
      "title": "Apple Fifth Avenue",
      "description": "The iconic glass cube Apple Store could be an interesting technology-focused visit during rainy weather.",
      "reasoning": "This aligns with your technology interest (0.78 confidence) and is free to visit.",
      "confidence": 0.75,
      "metadata": {
        "cost": "Free",
        "location": "767 5th Ave, New York, NY",
        "matches_traits": ["interests.technology"]
      }
    }
  ],
  "metadata": {
    "created_at": "ISO-8601 timestamp",
    "profile_attributes_used": ["interests.art", "interests.technology", "preferences.indoor_activities_on_rainy_days"],
    "context_factors_considered": ["weather.rainy", "time_available", "location"],
    "confidence_overall": 0.85
  }
}
```

## Feedback (Upcoming in V1)

### POST /api/v1/feedback

Submits user feedback about recommendations or digital twin interactions to improve the user model.

**Request:**
```json
{
  "reference_id": "uuid_of_recommendation_or_chat",
  "reference_type": "recommendation",
  "rating": 4,
  "feedback_text": "I really liked the MoMA suggestion, but it was a bit crowded today.",
  "metadata": {
    "selected_recommendation": 0,
    "user_action": "visited_location"
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "profile_updates": [
    {"attribute": "preferences.crowd_tolerance", "old_value": null, "new_value": "prefers_less_crowded", "confidence": 0.65}
  ],
  "metadata": {
    "created_at": "ISO-8601 timestamp"
  }
}
```

## Data Sources (Upcoming in V1)

Endpoints for managing data sources that feed the digital twin.

### GET /api/v1/sources

Retrieves all data sources connected to the user's digital twin.

**Request:**
```
GET /api/v1/sources
```

**Response:**
```json
{
  "sources": [
    {
      "id": "uuid",
      "type": "twitter",
      "name": "@username",
      "status": "active",
      "last_sync": "ISO-8601 timestamp",
      "metadata": {
        "items_count": 250,
        "traits_extracted": 15,
        "confidence_overall": 0.72
      },
      "settings": {
        "sync_frequency": "daily"
      }
    },
    {
      "id": "uuid",
      "type": "calendar",
      "name": "Work Calendar",
      "status": "active",
      "last_sync": "ISO-8601 timestamp",
      "metadata": {
        "items_count": 128,
        "traits_extracted": 8,
        "confidence_overall": 0.85
      },
      "settings": {
        "sync_frequency": "hourly",
        "earliest_date": "2023-01-01",
        "include_details": true
      }
    },
    {
      "id": "uuid",
      "type": "file_upload",
      "name": "resume.pdf",
      "status": "processed",
      "created_at": "ISO-8601 timestamp",
      "metadata": {
        "size": "125kb",
        "traits_extracted": 12,
        "confidence_overall": 0.91
      }
    }
  ],
  "metadata": {
    "total_count": 3,
    "source_diversity": 0.8,
    "last_updated": "ISO-8601 timestamp"
  }
}
```

### POST /api/v1/sources

Adds a new data source to the user's digital twin.

**Request:**
```json
{
  "type": "calendar",
  "credentials": {
    "token": "oauth_token",
    "refresh_token": "refresh_token"
  },
  "settings": {
    "sync_frequency": "daily",
    "earliest_date": "2023-01-01",
    "include_details": true
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "type": "calendar",
  "name": "Google Calendar",
  "status": "connected",
  "created_at": "ISO-8601 timestamp",
  "settings": {
    "sync_frequency": "daily",
    "earliest_date": "2023-01-01",
    "include_details": true
  },
  "next_sync": "ISO-8601 timestamp"
}
```

### PUT /api/v1/sources/{source_id}

Updates settings for an existing data source.

**Request:**
```json
{
  "settings": {
    "sync_frequency": "hourly",
    "include_details": false
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "type": "calendar",
  "updated_fields": ["settings.sync_frequency", "settings.include_details"],
  "metadata": {
    "updated_at": "ISO-8601 timestamp"
  }
}
```

### DELETE /api/v1/sources/{source_id}

Removes a data source from the user's digital twin.

**Request:**
```
DELETE /api/v1/sources/{source_id}
```

**Response:**
```json
{
  "status": "success",
  "message": "Data source removed",
  "id": "uuid"
}
```

### GET /api/v1/sources/{source_id}/status

Retrieves the current status of a data source, including sync progress.

**Request:**
```
GET /api/v1/sources/{source_id}/status
```

**Response:**
```json
{
  "id": "uuid",
  "type": "twitter",
  "status": "syncing",
  "progress": {
    "percent_complete": 75,
    "items_processed": 150,
    "estimated_completion": "ISO-8601 timestamp"
  },
  "last_successful_sync": "ISO-8601 timestamp",
  "error": null
}
```

### POST /api/v1/sources/{source_id}/sync

Triggers an immediate sync for a data source.

**Request:**
```
POST /api/v1/sources/{source_id}/sync
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Sync initiated",
  "task_id": "task-uuid",
  "estimated_completion": "ISO-8601 timestamp"
}
```
