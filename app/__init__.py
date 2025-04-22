"""Main app package."""

# Import worker tasks to ensure they're registered
from app.worker import celery_app

# Import task modules to ensure they're registered with Celery
import app.worker.tasks
import app.worker.tasks.conversation_tasks
