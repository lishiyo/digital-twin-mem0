from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import logging
import os
from pathlib import Path

from app.api.router import api_router
from app.core.config import settings
from app.scripts.create_test_user import create_test_user

logger = logging.getLogger(__name__)

# Get the base directory of the app
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Digital Twin API",
    description="API for Digital Twin",
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

# Mount static files directory
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Include API router
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


@app.get("/")
async def chat_page(request: Request):
    """Serve the chat interface."""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/knowledge")
async def knowledge_page(request: Request):
    """Serve the knowledge interface."""
    return templates.TemplateResponse("knowledge.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
