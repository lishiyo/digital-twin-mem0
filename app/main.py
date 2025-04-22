from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from app.api.router import api_router
from app.core.config import settings
from app.scripts.create_test_user import create_test_user

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Digital Twin & DAO API",
    description="API for Digital Twin & DAO Coordination",
    version="0.1.0",
)

# Set up CORS
origins = (
    [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
    if "," in settings.CORS_ORIGINS
    else [settings.CORS_ORIGINS]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.on_event("startup")
async def startup_db_client():
    """Run startup tasks - create test user for development."""
    try:
        await create_test_user()
        logger.info("Startup tasks completed")
    except Exception as e:
        logger.error(f"Error during startup: {e}")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
