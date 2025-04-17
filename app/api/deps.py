from collections.abc import Generator
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal

security = HTTPBearer()


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
