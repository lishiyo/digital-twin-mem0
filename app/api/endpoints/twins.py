from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

router = APIRouter()


@router.get("/{uid}/profile")
async def get_twin_profile(uid: str, current_user: dict = Depends(get_current_user)):
    """Get digital twin profile."""
    # This is a stub implementation
    return {"user_id": uid, "profile": "Twin profile will be implemented in a future task."}


@router.post("/{uid}/chat")
async def chat_with_twin(uid: str, message: str, current_user: dict = Depends(get_current_user)):
    """Chat with a digital twin."""
    # This is a stub implementation
    return {
        "user_id": uid,
        "message": message,
        "response": "Twin chat will be implemented in a future task.",
    }
