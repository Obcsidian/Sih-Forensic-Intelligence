from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models.user import User
from app.schemas.search import SearchHitResponse, SearchRequest
from app.security import require_any_role
from app.services import semantic_search

router = APIRouter(prefix="/cases/{case_id}/search", tags=["search"])


@router.post("", response_model=list[SearchHitResponse])
def search_case(
    case_id: int,
    body: SearchRequest,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[SearchHitResponse]:
    if not semantic_search.is_available():
        raise HTTPException(status_code=503, detail="Semantic search model dependencies are not installed")

    try:
        hits = semantic_search.search(session, case_id, body.query, top_k=body.top_k)
    except semantic_search.ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return [SearchHitResponse(**hit.__dict__) for hit in hits]
