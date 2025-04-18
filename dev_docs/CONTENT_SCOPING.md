# Content Scoping in Graphiti

This document explains how content is scoped and partitioned in the knowledge graph to support different visibility levels and access controls.

## Overview

The system supports three levels of content scoping:

1. **User-specific (Personal)**: Content visible only to the specific user who created it
2. **Twin-specific**: Content visible only in the context of a specific digital twin
3. **Global**: Content visible to all users and twins (shared knowledge)

Content scoping is implemented using a node tagging approach, where each node and relationship in Graphiti is tagged with metadata properties that define its scope and ownership.

## Implementation

Each node and relationship in the knowledge graph has the following scope-related properties:

- `scope`: A string value that can be one of: "user", "twin", or "global"
- `owner_id`: The ID of the owner (user_id or twin_id) or null for global content

These properties are used to filter query results to ensure users only see content they should have access to.

## Content Visibility Rules

The system follows these rules for content access:

1. **User-scoped content** is only visible to the owner specified in the `owner_id` field
2. **Twin-scoped content** is only visible in the context of the twin specified in the `owner_id` field
3. **Global content** is visible to all users and twins

When querying the knowledge graph, the system will automatically filter results based on the user context to include:
- The user's personal content (`scope="user"` AND `owner_id=<user_id>`)
- Global content (`scope="global"`)

## API Usage

### Ingestion Service

When processing files or directories, you can specify the scope and owner:

```python
# Process a personal file for a specific user
result = await ingestion_service.process_file(
    file_path="path/to/file.md",
    user_id="user123",
    scope="user",
    owner_id="user123"  # Can be omitted for user scope (defaults to user_id)
)

# Process global knowledge files
result = await ingestion_service.process_file(
    file_path="path/to/knowledge.md",
    user_id="admin",
    scope="global",
    owner_id=None  # Can be omitted for global scope
)

# Process twin-specific content
result = await ingestion_service.process_file(
    file_path="path/to/twin_data.md",
    user_id="admin",
    scope="twin",
    owner_id="twin123"
)
```

### Graphiti Service

When creating nodes or relationships directly:

```python
# Create a global entity
entity_id = await graphiti_service.create_entity(
    entity_type="Organization",
    properties={"name": "ACME Corp"},
    scope="global"
)

# Create a user-specific entity
entity_id = await graphiti_service.create_entity(
    entity_type="Person",
    properties={"name": "John Smith"},
    scope="user",
    owner_id="user123"
)
```

When searching:

```python
# Get all content accessible to a user (personal + global)
results = await graphiti_service.get_accessible_content(
    user_id="user123",
    query="search terms"
)

# Search specific scopes
results = await graphiti_service.search(
    query="search terms",
    user_id="user123",
    scope="global"  # Only search global content
)
```

## Command Line Usage

The `ingest_data_dir.py` script supports content scoping through command line arguments:

```bash
# Process files as global content
python app/scripts/ingest_data_dir.py --scope=global

# Process files as user-specific content
python app/scripts/ingest_data_dir.py --user-id=user123 --scope=user

# Process files as twin-specific content
python app/scripts/ingest_data_dir.py --scope=twin --owner-id=twin123
```

## Best Practices

1. Always specify the appropriate scope when ingesting content
2. For user-specific content, the `owner_id` will default to the provided `user_id` if not specified
3. For global content, set `scope="global"` and leave `owner_id` as None
4. For searching, use the `get_accessible_content` method to find all content a user should have access to
5. Be careful with twin-specific content - it should have a valid twin ID as its owner 