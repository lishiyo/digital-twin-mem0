"""Chat API endpoints for the digital twin."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
import asyncio
import logging
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, security
from app.services.agent.graph_agent import TwinAgent
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Model for the chat request
class ChatRequest(BaseModel):
    message: str

# Mock user for development/testing
MOCK_USER = {"id": "dev-user-for-testing", "name": "Dev User"}

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
            return MOCK_USER
    
    # No credentials provided, use mock user
    logger.warning("No authentication provided, using mock user")
    return MOCK_USER


@router.post("")
async def chat_with_twin(
    chat_request: ChatRequest,
    user_id: Optional[str] = Query(None, description="User ID to use (defaults to authenticated user)"),
    model_name: str = Query(getattr(settings, "CHAT_MODEL", "gpt-4o-mini"), description="Model to use for response generation"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Chat with the digital twin.
    
    This endpoint allows you to send a message to the digital twin agent
    and receive a response. The agent will use the user's personal knowledge base
    to inform its responses.
    """
    if not user_id:
        user_id = current_user.get("id", "dev-user-for-testing")
    
    try:
        # Initialize the agent
        agent = TwinAgent(user_id=user_id, model_name=model_name)
        
        # Process the message from the request body
        response = await agent.chat(chat_request.message)
        
        return {
            "user_message": chat_request.message,
            "twin_response": response,
            "user_id": user_id,
            "model_used": model_name
        }
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/stream")
async def stream_chat_with_twin(
    request: Request,
    chat_request: ChatRequest,
    user_id: Optional[str] = Query(None, description="User ID to use (defaults to authenticated user)"),
    model_name: str = Query(getattr(settings, "CHAT_MODEL", "gpt-4o-mini"), description="Model to use for response generation"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Chat with the digital twin and stream the response.
    
    This endpoint is similar to the regular chat endpoint but streams the response
    back to the client using server-sent events (SSE).
    
    Note: Streaming is not fully implemented yet in the agent, so this is a placeholder.
    """
    # This is a placeholder for the streaming endpoint
    # Will be implemented in the next task (Task 9: Chat Streaming)
    
    if not user_id:
        user_id = current_user.get("id", "dev-user-for-testing")
    
    # For now, just use the regular chat and return a non-streaming response
    try:
        # Initialize the agent
        agent = TwinAgent(user_id=user_id, model_name=model_name)
        
        # Process the message from the request body
        response = await agent.chat(chat_request.message)
        
        return {
            "user_message": chat_request.message,
            "twin_response": response,
            "user_id": user_id,
            "model_used": model_name,
            "streaming": False,
            "note": "Streaming is not yet implemented, this is a placeholder endpoint."
        }
    except Exception as e:
        logger.error(f"Error in stream chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        ) 