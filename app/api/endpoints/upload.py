import os
import uuid
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.constants import DEFAULT_USER
from app.worker import tasks
from app.services.ingestion import FileService
from app.services.ingestion.file_service import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional auth dependency for development
def get_optional_user(current_user: dict = Depends(get_current_user)):
    return current_user

async def get_current_user_or_mock():
    """
    Get the current user if authenticated, otherwise return a mock user.
    This is for development purposes only and should be replaced with proper auth in production.
    """
    # For now, just return the mock user directly without trying authentication
    # Remove this bypass and implement proper auth for production
    logger.warning("⚠️ AUTH BYPASSED - Using mock user - FOR DEVELOPMENT ONLY")
    return DEFAULT_USER


@router.post("")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    async_processing: bool = Form(True),
    scope: str = Form("user"),
    current_user: dict = Depends(get_current_user_or_mock)  # Use the optional auth
):
    """
    Upload a file for ingestion.
    
    Args:
        file: The file to upload
        async_processing: Whether to process the file asynchronously (default: True)
        scope: Content scope ("user", "twin", or "global", default: "user")
        current_user: Current authenticated user or mock user for development
        
    Returns:
        Upload result with file info and task ID if async
    """
    # Get user ID from authenticated user
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    # Initialize file service
    file_service = FileService()
    
    # Create unique filename to avoid collisions
    original_filename = file.filename
    file_extension = os.path.splitext(original_filename)[1].lower()
    
    # Check if file type is supported
    if file_extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415, 
            detail=f"Unsupported file type: {file_extension}. Supported types: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    rel_file_path = unique_filename
    abs_file_path = os.path.join(file_service.data_dir, unique_filename)
    
    # Create temporary file
    try:
        # Read file content
        content = await file.read()
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {len(content)} bytes (max: {max_size} bytes)"
            )
        
        # Write content to disk
        with open(abs_file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved to {abs_file_path}")
        
        # Calculate file hash for tracking
        file_hash = file_service._calculate_file_hash(abs_file_path)
        
        # Perform safety scan on the uploaded file
        is_safe, safety_error = file_service.scan_file_safety(rel_file_path)
        if not is_safe:
            # Remove the unsafe file
            try:
                os.remove(abs_file_path)
                logger.warning(f"Removed unsafe file {abs_file_path}: {safety_error}")
            except Exception as e:
                logger.error(f"Failed to remove unsafe file {abs_file_path}: {e}")
            
            raise HTTPException(
                status_code=400,
                detail=f"File safety check failed: {safety_error}"
            )
        
        # Process file
        if async_processing:
            # Launch Celery task for processing
            task = tasks.process_file.delay(rel_file_path, user_id, scope=scope, owner_id=user_id if scope == "user" else None)
            
            return {
                "status": "accepted",
                "message": "File uploaded and queued for processing",
                "file_details": {
                    "original_filename": original_filename,
                    "stored_filename": unique_filename,
                    "size": len(content),
                    "hash": file_hash,
                    "content_type": file.content_type,
                },
                "task_id": task.id,
                "user_id": user_id,
                "scope": scope,
            }
        else:
            # Run synchronously in request
            # We'll use background_tasks to avoid blocking the request,
            # but the client can still wait for the result
            background_tasks.add_task(
                tasks.process_file,
                rel_file_path,
                user_id,
                scope=scope,
                owner_id=user_id if scope == "user" else None
            )
            
            return {
                "status": "processing",
                "message": "File uploaded and is being processed",
                "file_details": {
                    "original_filename": original_filename,
                    "stored_filename": unique_filename,
                    "size": len(content),
                    "hash": file_hash,
                    "content_type": file.content_type,
                },
                "user_id": user_id,
                "scope": scope,
            }
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


@router.post("/batch")
async def upload_files(
    files: List[UploadFile] = File(...),
    async_processing: bool = Form(True),
    scope: str = Form("user"),
    current_user: dict = Depends(get_current_user_or_mock)
):
    """
    Upload multiple files for ingestion.
    
    Args:
        files: List of files to upload
        async_processing: Whether to process the files asynchronously (default: True)
        scope: Content scope ("user", "twin", or "global", default: "user")
        current_user: Current authenticated user or mock user for development
        
    Returns:
        List of upload results
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Get user ID from authenticated user
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    # Process each file
    results = []
    for file in files:
        try:
            # Use the single file endpoint logic
            result = await upload_file(
                background_tasks=BackgroundTasks(),
                file=file,
                async_processing=async_processing,
                scope=scope,
                current_user=current_user
            )
            results.append(result)
        except HTTPException as e:
            # Add file info to the error
            results.append({
                "status": "error",
                "filename": file.filename,
                "error": e.detail,
                "status_code": e.status_code
            })
        except Exception as e:
            # Add file info to the error
            results.append({
                "status": "error",
                "filename": file.filename,
                "error": str(e)
            })
    
    return {
        "status": "accepted" if any(r.get("status") == "accepted" for r in results) else "error",
        "message": f"Processed {len(results)} files",
        "results": results
    }


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user_or_mock)
):
    """
    Get the status of a file processing task.
    
    Args:
        task_id: Celery task ID
        current_user: Current authenticated user or mock user for development
        
    Returns:
        Task status and result if complete
    """
    from app.worker import celery_app
    
    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'status': 'pending',
                'message': 'Task is pending execution'
            }
        elif task.state == 'STARTED':
            response = {
                'status': 'processing',
                'message': 'Task is being processed'
            }
        elif task.state == 'SUCCESS':
            response = {
                'status': 'success',
                'message': 'Task completed successfully',
                'result': task.result
            }
        elif task.state == 'FAILURE':
            response = {
                'status': 'error',
                'message': 'Task failed',
                'error': str(task.result) if task.result else "Unknown error"
            }
        else:
            response = {
                'status': task.state,
                'message': 'Task is in progress'
            }
            
        return response
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")


@router.post("/process-directory")
async def trigger_directory_processing(
    directory: Optional[str] = Form(None),
    async_processing: bool = Form(True),
    scope: str = Form("user"),
    current_user: dict = Depends(get_current_user_or_mock)
):
    """
    Trigger processing of all files in a directory.
    
    Args:
        directory: Optional subdirectory to process (relative to data dir)
        async_processing: Whether to process the directory asynchronously (default: True)
        scope: Content scope ("user", "twin", or "global", default: "user")
        current_user: Current authenticated user or mock user for development
        
    Returns:
        Processing task details
    """
    # Get user ID from authenticated user
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        if async_processing:
            # Launch Celery task
            task = tasks.process_directory.delay(
                user_id,
                directory,
                scope=scope,
                owner_id=user_id if scope == "user" else None
            )
            
            return {
                "status": "accepted",
                "message": f"Directory processing queued: {directory or 'data'}",
                "task_id": task.id,
                "user_id": user_id,
                "scope": scope,
            }
        else:
            # Directly process directory
            background_tasks = BackgroundTasks()
            background_tasks.add_task(
                tasks.process_directory,
                user_id,
                directory,
                scope=scope,
                owner_id=user_id if scope == "user" else None
            )
            
            return {
                "status": "processing",
                "message": f"Directory processing started: {directory or 'data'}",
                "user_id": user_id,
                "scope": scope,
            }
    except Exception as e:
        logger.error(f"Error triggering directory processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process directory: {str(e)}")
