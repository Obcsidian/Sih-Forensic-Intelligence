from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.registry_artifact import RegistryArtifact
from app.models.user import User
from app.security import require_any_role

router = APIRouter(prefix="/cases/{case_id}", tags=["artifacts"])


@router.get("/registry-artifacts", response_model=list[RegistryArtifact])
def list_registry_artifacts(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[RegistryArtifact]:
    return session.exec(select(RegistryArtifact).where(RegistryArtifact.case_id == case_id)).all()
