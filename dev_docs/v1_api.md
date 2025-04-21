# Digital Twin API Reference

This document outlines the API endpoints for the Digital Twin v1 implementation, as well existing endpoints in v0. All endpoints are prefixed with `/api/v1`.

## User Profile (Upcoming in V1)

### GET /api/v1/profile

Retrieves the current user's profile information including preferences, skills, interests, and relationships.

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

### PUT /api/v1/profile

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

## Chat

### POST /api/v1/chat (already in v0, without context/metadata support)

Sends a message to the digital twin and receives a response. All conversations are stored for profile learning.

**Request:**
```json
POST /api/v1/chat
{
  "message": "What can you tell me about digital twins?"
}
```

Parameters:
- `model_name` (optional): Specific model to use (e.g., "gpt-4") if not default
- `user_id` (optional): Specific user ID to associate with the chat for dev purposes
- V1 upcoming parameters:
    - `context` (optional): Json blob of useful context
    - `metadata` (optional): Json blob of metadata

**Response:**
```json
{
  "user_message": "What can you tell me about digital twins?",
  "twin_response": "A digital twin is a virtual representation...",
  "user_id": "user-id",
  "model_used": "gpt-3.5-turbo"
}
```

Other examples:
**Request:**
```json
{
  "message": "Can you recommend some hiking trails near me?",
  "context": {
    "location": "San Francisco, CA",
    "weather": "sunny, 75°F",
    "time": "weekend morning"
  },
  "metadata": {
    "client_id": "web",
    "session_id": "uuid"
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "response": "Based on your location in San Francisco and your interest in hiking, I'd recommend the Lands End Trail which offers stunning views of the Golden Gate Bridge. Since it's a sunny weekend morning, it might be busy, so consider starting early.",
  "metadata": {
    "profile_attributes_used": ["interests.hiking", "preferences.outdoor_activity_level"],
    "confidence": 0.85,
    "sources": [
      {"type": "user_profile", "attribute": "interests.hiking"},
      {"type": "external_context", "attribute": "location"}
    ],
    "created_at": "ISO-8601 timestamp",
    "processed_traits": [
      {"name": "enjoys nature views", "confidence": 0.7, "will_add_to_profile": true}
    ]
  }
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

### Search API (already in v0)

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



## Recommendations (Upcoming in V1)

### POST /api/v1/recommendations

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
