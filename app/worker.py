"""Entry point for Celery worker."""

from app.worker import celery_app

# This is just a re-export of the celery_app for compatibility
# The actual configuration is in app.worker.celery_app

if __name__ == "__main__":
    celery_app.start()
