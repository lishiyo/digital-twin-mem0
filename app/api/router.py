from fastapi import APIRouter

from app.api.endpoints import health, proposals, twins, upload, search

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(twins.router, prefix="/twins", tags=["twins"])
api_router.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
