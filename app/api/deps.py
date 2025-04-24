from collections.abc import Generator
from typing import Annotated, Optional

from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.config import settings
from app.core.constants import DEFAULT_USER
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

security = HTTPBearer()
# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)


async def get_db() -> Generator[AsyncSession, None, None]:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)],
) -> dict:
    """Get the current authenticated user from JWT token."""
    try:
        # This is a simplified version without actual verification
        # In production, use the jose library to validate the token with Auth0
        payload = jwt.decode(
            credentials.credentials,
            "",  # This should be the public key from Auth0
            algorithms=settings.AUTH0_ALGORITHMS,
            options={"verify_signature": False},  # Only for development!
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        return {"id": user_id}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )


async def get_current_user_or_mock(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> dict:
    """Get the current authenticated user or a mock user for development.
    
    This is a utility function that can be used across all endpoints that
    need to support both authenticated users and development testing.
    
    Args:
        credentials: Optional HTTP auth credentials
        
    Returns:
        User dict with ID
    """
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
