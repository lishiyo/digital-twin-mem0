"""Endpoints for searching ingested content."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime, timezone

from app.api.deps import get_current_user, get_db, security
from app.services.memory import MemoryService
from app.services.graph import GraphitiService
from app.core.constants import DEFAULT_USER
from app.schemas.ingested_document import IngestedDocument
from app.api.deps import get_current_user_or_mock

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)

# Helper function to get memory service
def get_memory_service():
    """Get memory service instance."""
    return MemoryService()

@router.get("")
async def search_content(
    query: str = Query(..., description="Search query string"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of results to return"),
    search_type: str = Query("memory", description="Type of search: 'memory', 'graph', or 'both'"),
    metadata_filter: Optional[Dict[str, Any]] = None,
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


@router.get("/ingested-documents", response_model=List[IngestedDocument])
async def list_ingested_documents(
    user_id: str = Query("", title="User ID filter"),
    limit: int = Query(100, title="Limit of documents to return"),
    db: AsyncSession = Depends(get_db),
    memoryService: MemoryService = Depends(get_memory_service),
    current_user: dict = Depends(get_current_user_or_mock),
) -> List[IngestedDocument]:
    """
    List documents ingested into memory.
    
    Optionally filter by user ID.
    """
    try:
        # Use current user ID if not specified in query
        if not user_id:
            user_id = current_user.get("id", DEFAULT_USER["id"])
            
        logger.info(f"Listing ingested documents for user_id={user_id}, limit={limit}")
        
        # Get all memories for the user
        memories = await memoryService.get_all(
            user_id=user_id,
            limit=limit
        )
        
        if not memories:
            logger.warning(f"No memories found for user_id={user_id}")
            return []
            
        logger.info(f"Retrieved {len(memories)} memories for user_id={user_id}")
        
        # Process memories to documents using the class method
        documents = IngestedDocument.from_memories(memories, user_id)
        
        logger.info(f"Returning {len(documents)} documents")
        return documents
        
    except Exception as e:
        logger.exception(f"Error listing ingested documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}") 