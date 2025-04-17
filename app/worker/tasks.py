from app.worker import celery_app


@celery_app.task(name="process_file")
def process_file(file_path: str, user_id: str) -> dict:
    """Process an uploaded file and store in Mem0.

    This is a stub implementation that will be expanded in later tasks.
    """
    # In the real implementation, this would:
    # 1. Read the file
    # 2. Chunk it
    # 3. Store it in Mem0
    # 4. Optionally extract entities and store in Graphiti
    return {"status": "processed", "file_path": file_path, "user_id": user_id}
