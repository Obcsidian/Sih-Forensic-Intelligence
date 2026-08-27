import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.config import get_settings
from app.database import get_session
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.schemas.case import CaseCreateRequest, IngestSummaryResponse
from app.security import require_any_role, require_investigator
from app.services import audit_log
from app.services.e01_ingestion import E01_EXTENSIONS
from app.services.e01_ingestion import resolve_parser
from app.services.ufdr_ingestion import UFDR_EXTENSIONS
from app.worker import process_case_task, run_task

router = APIRouter(prefix="/cases", tags=["cases"])

UPLOAD_EXTENSIONS = E01_EXTENSIONS | UFDR_EXTENSIONS
UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024

# Multi-segment EWF acquisitions split across .E01/.E02/.../.S01/.S02/.../.EX01/.EX02/...
# -- pyewf.glob() auto-discovers sibling segments by filename once they're all in the
# same directory, so the upload endpoint accepts the whole set at once.
SEGMENT_EXTENSION_RE = re.compile(r"^\.(e|s|l|ex)(\d{2,3})$", re.IGNORECASE)


def _safe_filename(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "upload"


def _is_first_segment(suffix: str) -> bool:
    match = SEGMENT_EXTENSION_RE.match(suffix)
    return bool(match) and int(match.group(2)) == 1


@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreateRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
) -> Case:
    source = Path(body.source_path)
    if not source.exists():
        raise HTTPException(status_code=400, detail=f"source_path '{body.source_path}' does not exist")
    try:
        resolve_parser(source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    case = Case(name=body.name, description=body.description, source_path=str(source), created_by=user.id)
    session.add(case)
    session.commit()
    session.refresh(case)

    audit_log.append_entry(session, actor=user.username, action="case.create", case_id=case.id, payload={"name": case.name})
    return case


@router.post("/upload", response_model=Case, status_code=status.HTTP_201_CREATED)
async def upload_case(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
    name: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    description: Annotated[str, Form()] = "",
) -> Case:
    """Accepts one file (a .UFDR, or a single-segment .E01) or a whole set of
    multi-segment EWF files (.E01 + .E02 + .E03 + ...) uploaded together --
    pyewf auto-discovers sibling segments by filename as long as they all
    live in the same directory, so every file is saved there before ingest."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in UPLOAD_EXTENSIONS and not SEGMENT_EXTENSION_RE.match(suffix):
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' has an unsupported extension; expected a .E01/.S01/.L01/.EX01 image "
                f"(optionally with .E02/.E03/... segments) or a .UFDR/.UFD archive",
            )

    upload_dir = get_settings().storage_path / "uploads" / uuid.uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    for f in files:
        dest = upload_dir / _safe_filename(f.filename or "upload")
        with dest.open("wb") as out:
            while chunk := await f.read(UPLOAD_CHUNK_SIZE):
                out.write(chunk)
        await f.close()
        saved.append(dest)

    primary = next((p for p in saved if p.suffix.lower() in UFDR_EXTENSIONS), None)
    if primary is None:
        primary = next((p for p in saved if _is_first_segment(p.suffix.lower())), None)
    if primary is None:
        raise HTTPException(
            status_code=400,
            detail="Could not find a first-segment file among the uploaded files "
            "(expected one ending in .E01/.S01/.L01/.EX01 or a .UFDR/.UFD)",
        )

    try:
        resolve_parser(primary)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    case = Case(name=name, description=description, source_path=str(primary), created_by=user.id)
    session.add(case)
    session.commit()
    session.refresh(case)

    audit_log.append_entry(
        session, actor=user.username, action="case.create", case_id=case.id,
        payload={"name": case.name, "uploaded_files": [p.name for p in saved]},
    )
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

    parser = resolve_parser(Path(case.source_path))
    summary = parser.ingest(session, case, Path(case.source_path))

    run_task(process_case_task, case_id)

    return IngestSummaryResponse(**summary.__dict__)
