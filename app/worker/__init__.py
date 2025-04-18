"""Worker package for Celery tasks."""

# Import celery_app from the worker module for easy access
from app.worker import celery_app

__all__ = ["celery_app"]
