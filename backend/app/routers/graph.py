from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.models.user import User
from app.schemas.graph import GraphEdgeResponse, GraphNodeResponse, GraphResponse
from app.security import require_any_role
from app.services import entity_graph

router = APIRouter(prefix="/cases/{case_id}/graph", tags=["graph"])


@router.get("", response_model=GraphResponse)
def get_graph(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> GraphResponse:
    graph = entity_graph.build(session, case_id)
    return GraphResponse(
        nodes=[GraphNodeResponse(**n.__dict__) for n in graph.nodes],
        edges=[GraphEdgeResponse(**e.__dict__) for e in graph.edges],
    )
