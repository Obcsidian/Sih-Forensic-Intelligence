import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.config import get_settings
from app.database import get_session
from app.models.case import Case, CaseStatus
from app.models.data_source import DataSource, DataSourceStatus
from app.models.evidence_file import EvidenceFile
from app.models.timeline_event import TimelineEvent
from app.models.user import User
from app.schemas.case import CaseCreateRequest, IngestSummaryResponse
from app.security import require_any_role, require_investigator
from app.services import audit_log
from app.services.e01_ingestion import E01_EXTENSIONS, RAW_EXTENSIONS
from app.services.e01_ingestion import resolve_parser
from app.services.ingestion import EMAIL_EXTENSIONS
from app.services.ufdr_ingestion import UFDR_EXTENSIONS
from app.worker import process_case_task, run_task

router = APIRouter(prefix="/cases", tags=["cases"])

UPLOAD_EXTENSIONS = E01_EXTENSIONS | RAW_EXTENSIONS | UFDR_EXTENSIONS | EMAIL_EXTENSIONS
CONTAINER_EXTENSIONS = UFDR_EXTENSIONS | RAW_EXTENSIONS
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


def _segment_base_name(filename: str) -> str:
    """Strips a .E01/.E02/.../.UFDR-style suffix so 'nps.E01' and 'nps.E02'
    compare equal -- used to recognize an uploaded continuation segment as
    belonging to a data source that's already in the case."""
    p = Path(filename)
    suffix = p.suffix.lower()
    if suffix in UPLOAD_EXTENSIONS or SEGMENT_EXTENSION_RE.match(suffix):
        return p.stem
    return p.name


def _source_display_name(primary: Path, files: list[UploadFile]) -> str:
    """A directory primary (the loose-.eml upload shape) has no meaningful
    filename of its own -- it's a random uuid4 hex -- so give it a name
    that actually describes the upload instead."""
    if primary.is_dir():
        return f"{len(files)} email{'s' if len(files) != 1 else ''}"
    return primary.name


def _has_container_primary(files: list[UploadFile]) -> bool:
    """True if the batch includes a .UFDR/.UFD, a raw/VM disk image, or the
    first segment of a multi-segment E01 -- i.e. a single file (or set) that
    is itself the whole data source, as opposed to a batch of loose files
    like standalone .eml messages."""
    return any(
        Path(f.filename or "").suffix.lower() in CONTAINER_EXTENSIONS
        or _is_first_segment(Path(f.filename or "").suffix.lower())
        for f in files
    )


async def _save_upload_set(files: list[UploadFile]) -> Path:
    """Validates and saves an uploaded set to a fresh directory.

    Two shapes are accepted:
    - A container: one .UFDR/.UFD, a raw/VM disk image, or a first-segment
      .E01 (+ optional .E02/.E03/... segments) -- returns the path to that
      primary file.
    - A batch of loose .eml files (no container present) -- these have no
      single "primary" file the way a disk image does, so they're saved
      into an emails/ subdirectory and the directory itself is returned;
      resolve_parser() routes a directory to CaseFolderParser, which already
      knows to look for an emails/ folder.

    Raises HTTPException on a bad set."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in UPLOAD_EXTENSIONS and not SEGMENT_EXTENSION_RE.match(suffix):
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' has an unsupported extension; expected a .E01/.S01/.L01/.EX01 image "
                f"(optionally with .E02/.E03/... segments), a raw/dd or VM disk image "
                f"(.dd/.img/.raw/.001/.vmdk/.vhd/.vhdx), a .UFDR/.UFD archive, or one or more .eml email files",
            )

    upload_dir = get_settings().storage_path / "uploads" / uuid.uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)

    is_email_batch = not _has_container_primary(files) and all(
        Path(f.filename or "").suffix.lower() in EMAIL_EXTENSIONS for f in files
    )

    if is_email_batch:
        emails_dir = upload_dir / "emails"
        emails_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            dest = emails_dir / _safe_filename(f.filename or "upload")
            with dest.open("wb") as out:
                while chunk := await f.read(UPLOAD_CHUNK_SIZE):
                    out.write(chunk)
            await f.close()
        return upload_dir

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
        primary = next((p for p in saved if p.suffix.lower() in RAW_EXTENSIONS), None)
    if primary is None:
        primary = next((p for p in saved if _is_first_segment(p.suffix.lower())), None)
    if primary is None:
        raise HTTPException(
            status_code=400,
            detail="Could not find a first-segment file among the uploaded files "
            "(expected one ending in .E01/.S01/.L01/.EX01, a raw/dd or VM disk image, a .UFDR/.UFD, "
            "or one or more .eml files)",
        )

    try:
        resolve_parser(primary)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return primary


def _run_ingest(session: Session, user: User, case: Case, ds: DataSource) -> IngestSummaryResponse:
    ds.status = DataSourceStatus.ingesting
    case.status = CaseStatus.ingesting
    session.add(ds)
    session.add(case)
    session.commit()

    parser = resolve_parser(Path(ds.source_path))
    summary = parser.ingest(session, case, Path(ds.source_path), data_source_id=ds.id)

    extracted = (
        summary.contacts + summary.calls + summary.messages
        + summary.photos + summary.videos + summary.audio_files + summary.device_events
    )
    if summary.errors and extracted == 0:
        # Errors alone don't mean failure -- e01_ingestion.py logs plenty of
        # per-file warnings (oversized file skipped, unparsed artifact DB,
        # ...) during an otherwise-successful ingest. Zero of everything
        # *and* an error (e.g. "no readable filesystem found") means the
        # image genuinely couldn't be read -- surface that instead of a
        # falsely reassuring "ready".
        ds.status = DataSourceStatus.failed
        ds.error = "; ".join(summary.errors)
    else:
        ds.status = DataSourceStatus.ready
        ds.error = None
    session.add(ds)
    session.commit()

    audit_log.append_entry(
        session, actor=user.username, action="data_source.ingest", case_id=case.id,
        payload={"data_source_id": ds.id, "source_path": ds.source_path, **summary.__dict__},
    )

    run_task(process_case_task, case.id)

    return IngestSummaryResponse(**summary.__dict__)


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

    session.add(DataSource(case_id=case.id, name=source.name, source_path=str(source), created_by=user.id))
    session.commit()

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
    """Accepts one file (a .UFDR, a raw/dd or VM disk image, or a
    single-segment .E01), a whole set of multi-segment EWF files
    (.E01 + .E02 + .E03 + ...) uploaded together -- pyewf auto-discovers
    sibling segments by filename as long as they all live in the same
    directory, so every file is saved there before ingest -- or one or more
    loose .eml files with no disk image at all."""
    primary = await _save_upload_set(files)

    case = Case(name=name, description=description, source_path=str(primary), created_by=user.id)
    session.add(case)
    session.commit()
    session.refresh(case)

    ds_name = _source_display_name(primary, files)
    session.add(DataSource(case_id=case.id, name=ds_name, source_path=str(primary), created_by=user.id))
    session.commit()

    audit_log.append_entry(
        session, actor=user.username, action="case.create", case_id=case.id,
        payload={"name": case.name, "uploaded_files": [primary.name]},
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

    ds = session.exec(
        select(DataSource).where(DataSource.case_id == case_id).order_by(DataSource.id)
    ).first()
    if ds is None:
        # Safety net: a case somehow created without its initial DataSource row.
        ds = DataSource(case_id=case.id, name=Path(case.source_path).name, source_path=case.source_path, created_by=user.id)
        session.add(ds)
        session.commit()
        session.refresh(ds)

    return _run_ingest(session, user, case, ds)


@router.get("/{case_id}/data-sources", response_model=list[DataSource])
def list_data_sources(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[DataSource]:
    if session.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return session.exec(select(DataSource).where(DataSource.case_id == case_id).order_by(DataSource.id)).all()


async def _extend_data_source(session: Session, user: User, ds: DataSource, files: list[UploadFile]) -> DataSource:
    """Saves continuation segment(s) (.E02, .E03, ...) alongside a data
    source's existing first segment, so pyewf.glob() picks up the complete
    set on the next ingest. If that source already ran (partial, since a
    segment was missing), its previously-extracted evidence is wiped so the
    re-ingest with the complete image doesn't leave duplicates behind."""
    dest_dir = Path(ds.source_path).parent
    added_names: list[str] = []
    for f in files:
        dest = dest_dir / _safe_filename(f.filename or "upload")
        with dest.open("wb") as out:
            while chunk := await f.read(UPLOAD_CHUNK_SIZE):
                out.write(chunk)
        await f.close()
        added_names.append(dest.name)

    if ds.status != DataSourceStatus.created:
        old_evidence = session.exec(select(EvidenceFile).where(EvidenceFile.data_source_id == ds.id)).all()
        old_ids = [e.id for e in old_evidence]
        if old_ids:
            for event in session.exec(
                select(TimelineEvent).where(TimelineEvent.source_table == "evidencefile", TimelineEvent.source_id.in_(old_ids))
            ).all():
                session.delete(event)
            for evidence in old_evidence:
                session.delete(evidence)
        ds.status = DataSourceStatus.created
        ds.error = None
        session.add(ds)

    session.commit()
    session.refresh(ds)

    audit_log.append_entry(
        session, actor=user.username, action="data_source.extend", case_id=ds.case_id,
        payload={"data_source_id": ds.id, "added_files": added_names},
    )
    return ds


@router.post("/{case_id}/data-sources", response_model=DataSource, status_code=status.HTTP_201_CREATED)
async def add_data_source(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
    files: Annotated[list[UploadFile], File()],
) -> DataSource:
    """Adds another E01/UFDR/raw image (+ segments), or a batch of loose
    .eml files, to an already-open case, without touching its existing
    evidence. Call .../ingest on the returned row to actually parse it in.

    If the upload has no first-segment/UFDR/raw-image file and isn't an
    all-.eml batch, but a continuation segment
    (.E02, .E03, ...) matches a data source already in this case by name,
    it's treated as completing that existing source rather than a new one --
    matching that an investigator adding a missing segment later is
    completing a source, not starting a second copy of the same disk."""
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    is_email_batch = not _has_container_primary(files) and all(
        Path(f.filename or "").suffix.lower() in EMAIL_EXTENSIONS for f in files
    )
    has_primary = _has_container_primary(files) or is_email_batch

    if not has_primary:
        upload_bases = {_segment_base_name(f.filename or "") for f in files}
        existing_sources = session.exec(select(DataSource).where(DataSource.case_id == case_id)).all()
        match = next((ds for ds in existing_sources if _segment_base_name(Path(ds.source_path).name) in upload_bases), None)
        if match is not None:
            return await _extend_data_source(session, user, match, files)

    primary = await _save_upload_set(files)

    ds = DataSource(case_id=case.id, name=_source_display_name(primary, files), source_path=str(primary), created_by=user.id)
    session.add(ds)
    session.commit()
    session.refresh(ds)

    audit_log.append_entry(
        session, actor=user.username, action="data_source.add", case_id=case.id,
        payload={"data_source_id": ds.id, "name": ds.name},
    )
    return ds


@router.post("/{case_id}/data-sources/{data_source_id}/ingest", response_model=IngestSummaryResponse)
def ingest_data_source(
    case_id: int,
    data_source_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
) -> IngestSummaryResponse:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    ds = session.get(DataSource, data_source_id)
    if ds is None or ds.case_id != case_id:
        raise HTTPException(status_code=404, detail="Data source not found")
    if ds.status != DataSourceStatus.created:
        raise HTTPException(status_code=400, detail=f"Data source is already in status '{ds.status}'")

    return _run_ingest(session, user, case, ds)
