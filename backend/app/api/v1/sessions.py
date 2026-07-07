from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.session import (
    CreateSessionRequest,
    SessionResponse,
    SessionListResponse,
)
from app.models.enums import SessionStatus

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_or_create_user(db: AsyncSession, user_id: str) -> User:
    uid = UUID(user_id) if isinstance(user_id, str) else user_id
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=uid, email=f"{user_id}@localhost")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.get("")
async def list_sessions(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    uid = UUID(user_id) if isinstance(user_id, str) else user_id
    result = await db.execute(
        select(SessionModel).where(SessionModel.user_id == uid).order_by(SessionModel.created_at.desc())
    )
    sessions = result.scalars().all()
    return SessionListResponse(
        sessions=[_session_to_response(s) for s in sessions],
        total=len(sessions),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    await _get_or_create_user(db, user_id)
    uid = UUID(user_id) if isinstance(user_id, str) else user_id
    session = SessionModel(
        user_id=uid,
        status=SessionStatus.LIVE,
        language=body.language,
        config={"title": body.title},
        started_at=func.now(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _session_to_response(session)


@router.delete("/{session_id}")
async def archive_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.status = SessionStatus.ARCHIVED
    await db.commit()
    return {"status": "archived"}


def _session_to_response(s: SessionModel) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        title=s.config.get("title", "Untitled Session") if s.config else "Untitled Session",
        language=s.language,
        status=s.status,
        started_at=s.started_at,
        ended_at=s.ended_at,
        created_at=s.created_at,
        turn_count=0,
        duration_ms=0,
    )
