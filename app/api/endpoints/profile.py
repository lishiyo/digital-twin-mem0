from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_or_mock
from app.core.constants import DEFAULT_USER
from app.services.profile import ProfileService
from fastapi.security import HTTPBearer

router = APIRouter()

# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)

@router.get("")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_or_mock)
) -> Dict[str, Any]:
    """Get current user profile.
    
    Args:
        db: Database session
        current_user: Current user dict (from auth)
        
    Returns:
        Dictionary with profile data
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    profile_service = ProfileService(db)
    result = await profile_service.get_profile(user_id)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=404,
            detail=result["message"]
        )
    
    return result


@router.post("/clear")
async def clear_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_or_mock)
) -> Dict[str, Any]:
    """Clear current user profile.
    
    Args:
        db: Database session
        current_user: Current user dict (from auth)
        
    Returns:
        Dictionary with operation status
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    profile_service = ProfileService(db)
    result = await profile_service.clear_profile(user_id)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=400, 
            detail=result["message"]
        )
    
    return result

@router.delete("/trait/{trait_type}/{trait_name}")
async def delete_trait(
    trait_type: str,
    trait_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_or_mock)
) -> Dict[str, Any]:
    """Delete a specific trait from the current user profile.
    
    Args:
        trait_type: Type of trait (skills, interests, dislikes, attributes, preferences)
        trait_name: Name of the trait to delete (for preferences use format: "category.name")
        db: Database session
        current_user: Current user dict (from auth)
        
    Returns:
        Dictionary with operation status
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    profile_service = ProfileService(db)
    result = await profile_service.delete_trait(user_id, trait_type, trait_name)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
    
    return result 