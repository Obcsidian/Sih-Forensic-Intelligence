from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.transcript import Transcript
from app.models.user import User
from app.security import require_any_role

router = APIRouter(prefix="/cases/{case_id}/transcripts", tags=["transcripts"])


@router.get("", response_model=list[Transcript])
def list_transcripts(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
    q: str | None = None,
) -> list[Transcript]:
    query = select(Transcript).where(Transcript.case_id == case_id)
    if q:
        query = query.where(Transcript.text.contains(q))
    return session.exec(query).all()
