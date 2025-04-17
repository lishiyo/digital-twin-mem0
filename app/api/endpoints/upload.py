from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_current_user

router = APIRouter()


@router.post("")
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload a file for ingestion."""
    # This is a stub implementation
    content = await file.read()
    # In the real implementation, we would process and store the file
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "status": "File upload will be implemented in a future task.",
    }
