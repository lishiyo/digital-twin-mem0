"""Endpoints for searching ingested content."""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime, timezone
import logging

from app.api.deps import get_current_user, get_db, security
from app.services.memory import MemoryService
from app.services.graph import GraphitiService
from app.core.constants import DEFAULT_USER

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)

# Optional authentication dependency - enables testing in development
async def get_current_user_or_mock(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    """Get the current authenticated user or a mock user for development."""
    if credentials:
        try:
            return await get_current_user(credentials)
        except HTTPException:
            # Fall back to mock user if authentication fails
            logger.warning("Authentication failed, using mock user")
            return DEFAULT_USER
    
    # No credentials provided, use mock user
    logger.warning("No authentication provided, using mock user")
    return DEFAULT_USER


@router.get("")
async def search_content(
    query: str = Query(..., description="Search query string"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of results to return"),
    search_type: str = Query("memory", description="Type of search: 'memory', 'graph', or 'both'"),
    metadata_filter: Optional[Dict[str, Any]] = None,
    use_mock: bool = Query(False, description="Use mock responses for testing"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Search for ingested documents using semantic search.
    
    This endpoint allows you to verify that ingestion is working by searching through:
    - Mem0 for semantic vector search of document chunks
    - Graphiti for knowledge graph entity and relationship search
    - Or both combined
    """
    if not user_id:
        user_id = current_user.get("id", DEFAULT_USER["id"])
    
    results = {}
    errors = []
    
    # Create mock data if requested
    if use_mock:
        return create_mock_results(query, search_type, limit, user_id)
    
    # Initialize services
    memory_service = MemoryService()
    graphiti_service = GraphitiService()
    
    # Perform Mem0 search
    if search_type in ["memory", "both"]:
        try:
            memory_results = await memory_service.search(
                query=query,
                user_id=user_id,
                limit=limit,
                metadata_filter=metadata_filter
            )
            results["memory"] = memory_results
        except Exception as e:
            errors.append(f"Memory search error: {str(e)}")
            results["memory"] = []
    
    # Perform Graphiti search
    if search_type in ["graph", "both"]:
        try:
            # Entity search
            entity_results = await graphiti_service.node_search(
                query=query,
                limit=limit
            )
            results["entities"] = entity_results
            
            # General graph search
            graph_results = await graphiti_service.search(
                query=query,
                user_id=user_id if user_id else None,
                limit=limit
            )
            results["graph"] = graph_results
        except Exception as e:
            errors.append(f"Graph search error: {str(e)}")
            if "entities" not in results:
                results["entities"] = []
            if "graph" not in results:
                results["graph"] = []
    
    # Add errors to response if any
    if errors:
        results["errors"] = errors
    
    return results


@router.get("/ingested-documents")
async def list_ingested_documents(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of documents to return"),
    use_mock: bool = Query(False, description="Use mock responses for testing"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    List documents that have been ingested into the system.
    
    This endpoint retrieves information about documents that have been ingested,
    including metadata like titles, timestamps, and entity counts.
    """
    if not user_id:
        user_id = current_user.get("id", DEFAULT_USER["id"])
    
    # Create mock data if requested
    if use_mock:
        return {
            "total_documents": 5,
            "documents": [
                {
                    "id": f"mock-doc-{i+1}",
                    "title": f"Mock Document {i+1}",
                    "source": ["upload", "web", "system"][i % 3],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "chunk_count": (i+1) * 5,
                    "entity_count": (i+1) * 3,
                    "metadata": {
                        "user_id": user_id,
                        "filename": f"mock_document_{i+1}.md",
                        "size_bytes": (i+1) * 1024,
                    }
                }
                for i in range(5)
            ]
        }
    
    # Initialize memory service
    memory_service = MemoryService()
    
    try:
        # Use metadata filter to find only document-type memories
        metadata_filter = {"source": "document"}
        
        # Get all memories for the user with document source
        doc_memories = await memory_service.get_all(
            user_id=user_id,
            metadata_filter=metadata_filter
        )
        
        # Organize by document (using filename from metadata)
        documents = {}
        for memory in doc_memories:
            metadata = memory.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            
            if filename not in documents:
                documents[filename] = {
                    "id": memory.get("memory_id", "unknown"),
                    "title": filename,
                    "source": metadata.get("source", "unknown"),
                    "timestamp": metadata.get("created_at", datetime.now(timezone.utc).isoformat()),
                    "chunk_count": 0,
                    "metadata": metadata,
                    "chunks": []
                }
            
            # Increment chunk count and add chunk summary
            documents[filename]["chunk_count"] += 1
            if len(documents[filename]["chunks"]) < 5:  # Limit chunks list to 5
                chunk_info = {
                    "id": memory.get("memory_id", "unknown"),
                    "content_preview": memory.get("content", "")[:100] + "..." if memory.get("content") else "",
                    "importance": metadata.get("importance", 0.5)
                }
                documents[filename]["chunks"].append(chunk_info)
        
        # Convert to list and apply limit
        document_list = list(documents.values())[:limit]
        
        return {
            "total_documents": len(documents),
            "documents": document_list
        }
    except Exception as e:
        return {
            "error": f"Error retrieving ingested documents: {str(e)}",
            "documents": []
        }


def create_mock_results(query: str, search_type: str, limit: int, user_id: str) -> Dict[str, Any]:
    """Create mock search results for testing purposes."""
    results = {}
    
    if search_type in ["memory", "both"]:
        memory_results = []
        for i in range(min(limit, 3)):
            memory_results.append({
                "memory_id": f"mock-memory-{uuid.uuid4()}",
                "content": f"Mock memory result {i+1} for query: '{query}'",
                "similarity": round(0.95 - (i * 0.1), 2),
                "metadata": {
                    "user_id": user_id,
                    "source": "document",
                    "filename": f"mock_document_{i+1}.md",
                    "chunk_id": i+1
                }
            })
        results["memory"] = memory_results
    
    if search_type in ["graph", "both"]:
        # Mock entity results
        entity_results = []
        entity_types = ["Person", "Organization", "Document", "Location", "Technology"]
        
        for i in range(min(limit, 3)):
            entity_type = entity_types[i % len(entity_types)]
            entity_results.append({
                "uuid": str(uuid.uuid4()),
                "name": f"Mock {entity_type} Entity {i+1}",
                "summary": f"Mock entity related to '{query}'",
                "labels": [entity_type],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "attributes": {
                    "relevance": round(0.9 - (i * 0.1), 2),
                    "source": "mock_data"
                }
            })
        results["entities"] = entity_results
        
        # Mock graph results
        graph_results = []
        for i in range(min(limit, 3)):
            graph_results.append({
                "uuid": str(uuid.uuid4()),
                "fact": f"Mock graph fact {i+1} related to '{query}'",
                "score": round(0.9 - (i * 0.1), 2),
                "valid_from": datetime.now(timezone.utc).isoformat(),
                "valid_to": None
            })
        results["graph"] = graph_results
    
    return results 