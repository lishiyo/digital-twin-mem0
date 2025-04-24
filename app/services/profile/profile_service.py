from typing import Dict, Any, Optional, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.models.user import User
from app.db.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

class ProfileService:
    """Service for managing UserProfile data."""
    
    def __init__(self, db_session: AsyncSession):
        """Initialize with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    async def get_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile data.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with profile data
        """
        try:
            # Query user with profile
            query = (
                select(User)
                .where(User.id == user_id)
                .options(joinedload(User.profile))
            )
            
            # Execute the query
            result = await self.db.execute(query)
            user = result.unique().scalars().first()
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return {"status": "error", "message": "User not found"}
            
            profile = user.profile
            
            if not profile:
                logger.warning(f"Profile for user {user_id} not found")
                return {"status": "error", "message": "Profile not found"}
            
            # Format profile data
            profile_data = {
                "id": profile.id,
                "user_id": profile.user_id,
                "preferences": profile.preferences or {},
                "interests": profile.interests or [],
                "skills": profile.skills or [],
                "dislikes": profile.dislikes or [],
                "attributes": profile.attributes or [],
                "communication_style": profile.communication_style or {},
                "key_relationships": profile.key_relationships or [],
                "last_updated_source": profile.last_updated_source,
                "confidence_score": profile.confidence_score,
                "created_at": profile.created_at.isoformat() if profile.created_at else None,
                "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
            }
            
            # Get trait counts
            profile_data["stats"] = {
                "skills_count": len(profile.skills) if isinstance(profile.skills, list) else 0,
                "interests_count": len(profile.interests) if isinstance(profile.interests, list) else 0,
                "preferences_count": sum(len(prefs) for _, prefs in profile.preferences.items()) if isinstance(profile.preferences, dict) else 0,
                "dislikes_count": len(profile.dislikes) if isinstance(profile.dislikes, list) else 0,
                "attributes_count": len(profile.attributes) if isinstance(profile.attributes, list) else 0,
                "relationships_count": len(profile.key_relationships) if isinstance(profile.key_relationships, list) else 0,
            }
            
            return {"status": "success", "profile": profile_data}
            
        except Exception as e:
            logger.error(f"Error getting profile for user {user_id}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def clear_profile(self, user_id: str) -> Dict[str, Any]:
        """Clear user profile data.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with operation status
        """
        try:
            # Query user with profile
            query = (
                select(User)
                .where(User.id == user_id)
                .options(joinedload(User.profile))
            )
            
            # Execute the query
            result = await self.db.execute(query)
            user = result.unique().scalars().first()
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return {"status": "error", "message": "User not found"}
            
            profile = user.profile
            
            if not profile:
                logger.warning(f"Profile for user {user_id} not found")
                return {"status": "error", "message": "Profile not found"}
            
            # Reset profile fields
            profile.preferences = {}
            profile.interests = []
            profile.skills = []
            profile.dislikes = []
            profile.attributes = []
            profile.communication_style = {}
            profile.key_relationships = []
            profile.last_updated_source = "manual_reset"
            
            # Commit changes
            await self.db.commit()
            
            return {"status": "success", "message": "Profile cleared successfully"}
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error clearing profile for user {user_id}: {str(e)}")
            return {"status": "error", "message": str(e)} 