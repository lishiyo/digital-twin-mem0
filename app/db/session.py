from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from contextlib import asynccontextmanager, contextmanager

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,
    future=True,
)

# Create a synchronous engine for use in Celery tasks
sync_engine = create_engine(
    str(settings.SYNC_SQLALCHEMY_DATABASE_URI),
    echo=False,
    future=True,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Create synchronous session factory
SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    autoflush=False,
)

# Create a context manager for async database sessions
@asynccontextmanager
async def get_async_session() -> AsyncSession:
    """Yield an async database session."""
    async_session = AsyncSessionLocal()
    try:
        yield async_session
        await async_session.commit()
    except Exception:
        await async_session.rollback()
        raise
    finally:
        await async_session.close()

# Create a context manager for synchronous database sessions
@contextmanager
def get_db_session() -> Session:
    """Yield a synchronous database session for use in Celery tasks."""
    db_session = SyncSessionLocal()
    try:
        yield db_session
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
