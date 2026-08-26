"""Aggregates flagged evidence + AI outputs into an exportable HTML/PDF report."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import Session, func, select

from app.config import get_settings
from app.models.call import Call
from app.models.case import Case
from app.models.contact import Contact
from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.models.message import Message
from app.models.person import Person
from app.models.report import Report
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.models.transcript import Transcript
from app.services import audit_log, redaction

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape())


def _gather_stats(session: Session, case_id: int) -> dict:
    def count(stmt) -> int:
        return session.exec(stmt).one()

    return {
        "evidence_count": count(select(func.count()).select_from(EvidenceFile).where(EvidenceFile.case_id == case_id)),
        "photo_count": count(
            select(func.count()).select_from(EvidenceFile).where(
                EvidenceFile.case_id == case_id, EvidenceFile.kind == EvidenceKind.photo
            )
        ),
        "audio_count": count(
            select(func.count()).select_from(EvidenceFile).where(
                EvidenceFile.case_id == case_id, EvidenceFile.kind == EvidenceKind.audio
            )
        ),
        "person_count": count(select(func.count()).select_from(Person).where(Person.case_id == case_id)),
        "message_count": count(select(func.count()).select_from(Message).where(Message.case_id == case_id)),
        "call_count": count(select(func.count()).select_from(Call).where(Call.case_id == case_id)),
        "transcript_count": count(select(func.count()).select_from(Transcript).where(Transcript.case_id == case_id)),
        "anomaly_count": count(
            select(func.count()).select_from(TimelineEvent).where(
                TimelineEvent.case_id == case_id, TimelineEvent.event_type == TimelineEventType.anomaly
            )
        ),
        "nsfw_flagged_count": count(
            select(func.count()).select_from(EvidenceFile).where(
                EvidenceFile.case_id == case_id, EvidenceFile.nsfw_flagged.is_(True)
            )
        ),
    }


def generate_report(
    session: Session, case_id: int, *, redacted: bool = False, generated_by_username: str = "system"
) -> Report:
    case = session.get(Case, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} not found")

    people = session.exec(select(Person).where(Person.case_id == case_id)).all()
    anomalies = session.exec(
        select(TimelineEvent)
        .where(TimelineEvent.case_id == case_id, TimelineEvent.event_type == TimelineEventType.anomaly)
        .order_by(TimelineEvent.timestamp.asc())
    ).all()
    timeline = session.exec(
        select(TimelineEvent).where(TimelineEvent.case_id == case_id).order_by(TimelineEvent.timestamp.asc()).limit(200)
    ).all()
    stats = _gather_stats(session, case_id)

    if redacted:
        contacts = session.exec(select(Contact).where(Contact.case_id == case_id)).all()
        names = [c.name for c in contacts if c.name]
        timeline = [
            TimelineEvent(**{**event.model_dump(), "summary": redaction.redact_text(event.summary, names)})
            for event in timeline
        ]
        anomalies = [
            TimelineEvent(**{**event.model_dump(), "summary": redaction.redact_text(event.summary, names)})
            for event in anomalies
        ]

    template = _env.get_template("report_template.html")
    html = template.render(
        case=case,
        stats=stats,
        people=people,
        anomalies=anomalies,
        timeline=timeline,
        redacted=redacted,
        generated_at=datetime.now(timezone.utc).isoformat(),
        generated_by=generated_by_username,
    )

    settings = get_settings()
    output_dir = settings.storage_path / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    html_path = output_dir / f"{file_id}.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path: str | None = None
    try:
        from xhtml2pdf import pisa

        pdf_file = output_dir / f"{file_id}.pdf"
        with pdf_file.open("wb") as fh:
            pisa.CreatePDF(html, dest=fh)
        pdf_path = str(pdf_file)
    except ImportError:
        pdf_path = None

    report = Report(case_id=case_id, redacted=redacted, html_path=str(html_path), pdf_path=pdf_path)
    session.add(report)
    session.commit()
    session.refresh(report)

    audit_log.append_entry(
        session,
        actor=generated_by_username,
        action="report.generate",
        case_id=case_id,
        payload={"redacted": redacted, "report_id": report.id},
    )
    return report
