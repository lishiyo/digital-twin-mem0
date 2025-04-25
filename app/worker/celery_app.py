"""Celery app configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "app.worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.worker.tasks",
        "app.worker.tasks.conversation_tasks",  # Include the specific conversation tasks module
        "app.worker.tasks.file_tasks",  # Add the file_tasks module
        "app.worker.tasks.graphiti_tasks",  # Also add the graphiti_tasks module for completeness
    ],
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
) 