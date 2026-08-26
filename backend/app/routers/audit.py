from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.audit_log import AuditLogEntry
from app.models.user import User
from app.schemas.audit import ChainVerificationResponse
from app.security import require_any_role
from app.services import audit_log

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogEntry])
def list_audit_log(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
    case_id: int | None = None,
) -> list[AuditLogEntry]:
    query = select(AuditLogEntry).order_by(AuditLogEntry.id.asc())
    if case_id is not None:
        query = query.where(AuditLogEntry.case_id == case_id)
    return session.exec(query).all()


@router.get("/verify", response_model=ChainVerificationResponse)
def verify_audit_chain(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> ChainVerificationResponse:
    result = audit_log.verify_chain(session)
    return ChainVerificationResponse(**result.__dict__)
