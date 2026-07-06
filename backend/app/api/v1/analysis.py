from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user

router = APIRouter(prefix="/sessions/{session_id}/analysis", tags=["analysis"])


@router.get("")
async def get_analysis_report(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
) -> dict:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
) -> dict:
    return {
        "session_id": str(session_id),
        "status": "accepted",
        "message": "Analysis pipeline triggered",
    }
