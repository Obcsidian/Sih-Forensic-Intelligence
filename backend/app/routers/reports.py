from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.report import Report
from app.models.user import User
from app.schemas.reports import GenerateReportRequest
from app.security import require_reviewer_or_above
from app.services import report_generator

router = APIRouter(prefix="/cases/{case_id}/reports", tags=["reports"])


@router.get("", response_model=list[Report])
def list_reports(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_reviewer_or_above)],
) -> list[Report]:
    return session.exec(select(Report).where(Report.case_id == case_id).order_by(Report.created_at.desc())).all()


@router.post("", response_model=Report)
def generate_report(
    case_id: int,
    body: GenerateReportRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_reviewer_or_above)],
) -> Report:
    return report_generator.generate_report(
        session, case_id, redacted=body.redacted, generated_by_username=user.username
    )


@router.get("/{report_id}/download")
def download_report(
    case_id: int,
    report_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_reviewer_or_above)],
    fmt: str = "html",
) -> FileResponse:
    report = session.get(Report, report_id)
    if report is None or report.case_id != case_id:
        raise HTTPException(status_code=404, detail="Report not found")

    if fmt == "pdf":
        if not report.pdf_path:
            raise HTTPException(status_code=404, detail="PDF export not available (xhtml2pdf not installed at generation time)")
        return FileResponse(report.pdf_path, media_type="application/pdf", filename=f"case-{case_id}-report-{report_id}.pdf")

    return FileResponse(report.html_path, media_type="text/html", filename=f"case-{case_id}-report-{report_id}.html")
