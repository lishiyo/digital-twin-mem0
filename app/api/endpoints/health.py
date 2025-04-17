from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter()


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Health check endpoint that verifies database connection."""
    try:
        # Check if we can connect to the database
        await db.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
    }
