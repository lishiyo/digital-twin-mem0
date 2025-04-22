"""API router."""

from fastapi import APIRouter

from app.api.endpoints import auth, chat, memory, upload, search

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(search.router, prefix="/search", tags=["search"]) 