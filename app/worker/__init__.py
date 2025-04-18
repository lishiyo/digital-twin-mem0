"""Worker package for Celery tasks."""

# Import the celery app directly from app.worker
from app.worker.celery_app import celery_app

__all__ = ["celery_app"]
