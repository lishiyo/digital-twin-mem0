"""Graph API endpoints for accessing the knowledge graph."""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional, Any
import logging

from app.api.deps import get_current_user, get_db, security
from app.core.constants import DEFAULT_USER
from app.services.graph import GraphitiService, ContentScope
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_or_mock

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)

@router.get("/nodes")
async def list_nodes(
    limit: int = Query(10, description="Maximum number of nodes to return"),
    offset: int = Query(0, description="Offset for pagination"),
    query: Optional[str] = Query(None, description="Optional search query"),
    node_type: Optional[str] = Query(None, description="Optional node type filter"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    List graph nodes with pagination.
    
    Returns a paginated list of nodes (entities) from the knowledge graph,
    optionally filtered by a search query or node type.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        graphiti_service = GraphitiService()
        
        if query:
            # If a query is provided, use search
            # node_search doesn't support offset, so we need to get enough results and paginate manually
            search_limit = limit + offset
            
            # Pass owner_id and scope to node_search
            # For search, let's assume we want the user's nodes + global nodes
            # This means we don't filter by scope/owner directly in node_search,
            # but rely on its internal logic (needs verification if it supports this)
            # or filter afterward. Let's try passing user_id first.
            nodes = await graphiti_service.node_search(
                query=query,
                limit=search_limit
            )
            
            # Apply node_type filtering manually if specified
            if node_type and nodes:
                nodes = [node for node in nodes if node_type in node.get("labels", [])]
                
            # Apply pagination manually
            if len(nodes) > offset:
                nodes = nodes[offset:offset + limit]
            else:
                nodes = []
        else:
            # Otherwise, list all nodes (this method already supports offset)
            # Allow fetching user-owned nodes. Consider adding global scope if needed.
            nodes = await graphiti_service.list_nodes(
                limit=limit,
                offset=offset,
                node_type=node_type,
                scope="user", # Keep as USER for now, could be made flexible
                owner_id=user_id
            )
        
        return {
            "nodes": nodes,
            "total": len(nodes),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error listing graph nodes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list graph nodes: {str(e)}"
        )


@router.get("/relationships")
async def list_relationships(
    limit: int = Query(10, description="Maximum number of relationships to return"),
    offset: int = Query(0, description="Offset for pagination"),
    query: Optional[str] = Query(None, description="Optional search query"),
    rel_type: Optional[str] = Query(None, description="Optional relationship type filter"),
    scope: Optional[str] = Query(None, description="Optional scope filter (e.g., user, global)"),
    owner_id: Optional[str] = Query(None, description="Optional owner ID filter"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    List graph relationships with pagination.
    
    Returns a paginated list of relationships from the knowledge graph,
    optionally filtered by a search query or relationship type.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    logger.info(f'query: {query} rel_type: {rel_type} limit: {limit} offset: {offset}')
    
    # Determine scope and owner_id for filtering
    # If not provided in query params, default to the current user's scope
    filter_scope = scope if scope else "user"
    filter_owner_id = owner_id if owner_id else user_id
    
    # If scope is explicitly set to global, owner_id should be ignored/None
    if filter_scope == "global":
        filter_owner_id = None
        
    try:
        graphiti_service = GraphitiService()
        
        relationships = await graphiti_service.list_relationships(
            limit=limit,
            offset=offset,
            rel_type=rel_type,
            query=query,
            scope=filter_scope,
            owner_id=filter_owner_id
        )
        
        return {
            "relationships": relationships,
            "total": len(relationships),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error listing graph relationships: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list graph relationships: {str(e)}"
        )


@router.get("/node/{node_id}")
async def get_node_by_id(
    node_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Get a specific node (entity) by its ID.
    
    Retrieves a single node from the knowledge graph by its ID.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        graphiti_service = GraphitiService()
        node = await graphiti_service.get_node(node_id)
        
        if not node:
            raise HTTPException(
                status_code=404,
                detail=f"Node {node_id} not found"
            )
        
        return node
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching node {node_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch node: {str(e)}"
        )


@router.delete("/node/{node_id}", status_code=200)
async def delete_node_by_id_endpoint(
    node_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Delete a specific node (entity) by its UUID.
    
    Deletes a single node and its relationships from the knowledge graph.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        graphiti_service = GraphitiService()
        result = await graphiti_service.delete_node_by_uuid(node_id)
        
        if result.get("error"):
             raise HTTPException(
                status_code=500,
                detail=f"Failed to delete node: {result.get('error')}"
            )
            
        if not result.get("success"):
             raise HTTPException(
                status_code=404, # Assume failure means not found
                detail=f"Node {node_id} not found or could not be deleted"
            )
        
        return {"status": "success", "message": f"Node {node_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting node {node_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete node: {str(e)}"
        )


@router.get("/relationship/{relationship_id}")
async def get_relationship_by_id(
    relationship_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Get a specific relationship by its ID.
    
    Retrieves a single relationship from the knowledge graph by its ID.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        graphiti_service = GraphitiService()
        relationship = await graphiti_service.get_relationship(relationship_id)
        
        if not relationship:
            raise HTTPException(
                status_code=404,
                detail=f"Relationship {relationship_id} not found"
            )
        
        return relationship
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching relationship {relationship_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch relationship: {str(e)}"
        )


@router.delete("/relationship/{relationship_id}", status_code=200)
async def delete_relationship_by_id_endpoint(
    relationship_id: str,
    logical: bool = Query(True, description="Perform logical delete (set valid_to) instead of physical delete"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Delete a specific relationship by its UUID.
    
    Allows for logical deletion (default) or physical deletion.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        graphiti_service = GraphitiService()
        result = await graphiti_service.delete_relationship_by_uuid(
            uuid=relationship_id, 
            logical_delete=logical
        )
        
        if result.get("error"):
             raise HTTPException(
                status_code=500,
                detail=f"Failed to delete relationship: {result.get('error')}"
            )
            
        if not result.get("success"):
             raise HTTPException(
                status_code=404, # Assume failure means not found
                detail=f"Relationship {relationship_id} not found or could not be deleted"
            )
        
        delete_type = "Logically" if logical else "Physically"
        return {"status": "success", "message": f"{delete_type} deleted relationship {relationship_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting relationship {relationship_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete relationship: {str(e)}"
        ) 