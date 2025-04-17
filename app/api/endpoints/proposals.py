from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

router = APIRouter()


@router.get("/open")
async def get_open_proposals(current_user: dict = Depends(get_current_user)):
    """Get open proposals."""
    # This is a stub implementation
    return {"proposals": [{"id": 1, "title": "Test Proposal", "status": "open"}]}


@router.get("/{pid}/status")
async def get_proposal_status(pid: int, current_user: dict = Depends(get_current_user)):
    """Get proposal status."""
    # This is a stub implementation
    return {"id": pid, "title": "Test Proposal", "status": "open"}
