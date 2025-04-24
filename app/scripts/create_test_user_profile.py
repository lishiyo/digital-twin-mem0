#!/usr/bin/env python
"""
Script to create a user profile for the test user
"""

import sys
import os
import logging
from sqlalchemy import select
import uuid  # Add import for UUID generation

# Add the parent directory to sys.path to allow importing from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.session import get_db_session
from app.db.models.user import User
from app.db.models.user_profile import UserProfile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from app.core.constants import DEFAULT_USER_ID, DEFAULT_USER_NAME

TEST_USER_ID = DEFAULT_USER_ID

def create_test_user_profile():
    """Create or update the test user profile."""
    try:
        with get_db_session() as db:
            # Check if user exists
            query = select(User).where(User.id == TEST_USER_ID)
            result = db.execute(query)
            user = result.scalars().first()
            
            if not user:
                # Create test user
                logger.info(f"Creating test user with ID {TEST_USER_ID}")
                user = User(
                    id=TEST_USER_ID,
                    email="test@example.com",
                    name="Test User",
                    is_active=True
                )
                db.add(user)
                db.flush()  # Flush to get the user ID
            else:
                logger.info(f"Found existing test user: {user.id}")
                
            # Check if user profile exists
            if user.profile:
                logger.info(f"User profile already exists for {TEST_USER_ID}")
                return user.profile
                
            # Create user profile
            logger.info(f"Creating user profile for {TEST_USER_ID}")
            profile = UserProfile(
                id=str(uuid.uuid4()),  # Generate a new UUID for the profile
                user_id=user.id,
                # Initialize with empty arrays/objects
                skills=[],
                interests=[],
                preferences={},
                dislikes=[],
                attributes=[],
                communication_style={
                    "preferred_tone": "friendly",
                    "detailed_responses": True
                }
            )
            
            db.add(profile)
            db.commit()
            
            logger.info(f"Successfully created user profile for {TEST_USER_ID}")
            return profile
            
    except Exception as e:
        logger.error(f"Error creating test user profile: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting test user profile creation script")
    try:
        profile = create_test_user_profile()
        logger.info(f"Test user profile created successfully with ID: {profile.id if profile else 'None'}")
    except Exception as e:
        logger.error(f"Failed to create test user profile: {e}")
        sys.exit(1)
    
    logger.info("Script completed successfully")
    sys.exit(0) 