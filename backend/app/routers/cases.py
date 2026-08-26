from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.schemas.case import CaseCreateRequest, IngestSummaryResponse
from app.security import require_any_role, require_investigator
from app.services import audit_log
from app.services.ingestion import CaseFolderParser
from app.worker import process_case_task, run_task

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreateRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
) -> Case:
    source = Path(body.source_path)
    if not source.exists() or not source.is_dir():
        raise HTTPException(status_code=400, detail=f"source_path '{body.source_path}' is not a readable directory")

    case = Case(name=body.name, description=body.description, source_path=str(source), created_by=user.id)
    session.add(case)
    session.commit()
    session.refresh(case)

    audit_log.append_entry(session, actor=user.username, action="case.create", case_id=case.id, payload={"name": case.name})
    return case


@router.get("", response_model=list[Case])
def list_cases(
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[Case]:
    return session.exec(select(Case).order_by(Case.created_at.desc())).all()


@router.get("/{case_id}", response_model=Case)
def get_case(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/ingest", response_model=IngestSummaryResponse)
def ingest_case(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
) -> IngestSummaryResponse:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != CaseStatus.created:
        raise HTTPException(status_code=400, detail=f"Case is already in status '{case.status}'")

    case.status = CaseStatus.ingesting
    session.add(case)
    session.commit()

    summary = CaseFolderParser().ingest(session, case, Path(case.source_path))

    run_task(process_case_task, case_id)

    return IngestSummaryResponse(**summary.__dict__)
