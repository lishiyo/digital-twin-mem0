from fastapi import APIRouter

from app.api.endpoints import health, twins, upload, search, chat, memory, graph, profile

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(twins.router, prefix="/twins", tags=["twins"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
