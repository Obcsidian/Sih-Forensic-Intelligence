from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.evidence_file import EvidenceFile
from app.models.user import User
from app.security import require_any_role, require_reviewer_or_above
from app.services import audit_log

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceFile])
def list_evidence(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
    nsfw_flagged: bool | None = None,
) -> list[EvidenceFile]:
    query = select(EvidenceFile).where(EvidenceFile.case_id == case_id)
    if nsfw_flagged is not None:
        query = query.where(EvidenceFile.nsfw_flagged == nsfw_flagged)
    return session.exec(query).all()


@router.get("/{evidence_id}/file")
def get_evidence_file(
    case_id: int,
    evidence_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> FileResponse:
    evidence = session.get(EvidenceFile, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence file not found")
    return FileResponse(evidence.original_path)


@router.post("/{evidence_id}/nsfw-review", response_model=EvidenceFile)
def mark_nsfw_reviewed(
    case_id: int,
    evidence_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_reviewer_or_above)],
) -> EvidenceFile:
    evidence = session.get(EvidenceFile, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    evidence.nsfw_reviewed = True
    session.add(evidence)
    session.commit()
    session.refresh(evidence)

    audit_log.append_entry(
        session, actor=user.username, action="nsfw.review", case_id=case_id, payload={"evidence_id": evidence_id}
    )
    return evidence
