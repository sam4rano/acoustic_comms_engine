from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(user_id: str = Depends(get_current_user)) -> dict:
    return {"sessions": [], "total": 0}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(user_id: str = Depends(get_current_user)) -> dict:
    return {"id": "stub-id", "status": "created"}


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
) -> dict:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.delete("/{session_id}")
async def archive_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
) -> dict:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
