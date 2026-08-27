"""AI-powered forensic report generation.

Uses the AI gateway to generate structured investigation reports from
case evidence, timeline, and AI analysis results. Falls back to a
template-based report when the gateway is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models.call import Call
from app.models.contact import Contact
from app.models.evidence_file import EvidenceFile
from app.models.message import Message
from app.models.person import Person
from app.models.timeline_event import TimelineEvent
from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)

REPORT_PROMPT = (
    "You are a senior digital forensic examiner writing an investigation report. "
    "Using the provided case data, produce a structured report in the following format "
    "(use markdown):\n\n"
    "## Case Summary\n\n"
    "## Evidence Overview\n\n"
    "## Key Findings\n\n"
    "## Timeline of Significant Events\n\n"
    "## Persons of Interest\n\n"
    "## Anomalies and Flags\n\n"
    "## Recommendations\n\n"
    "Keep the report professional, factual, and concise. Do not speculate beyond the data."
)


def _build_case_context(session: Session, case_id: int) -> str:
    case = session.get(select(EvidenceFile).where(EvidenceFile.case_id == case_id).limit(1).with_only_columns(
        EvidenceFile.case_id
    ).execution_options(synchronize_session="fetch")).first()

    evidence = session.exec(select(EvidenceFile).where(EvidenceFile.case_id == case_id)).all()
    messages = session.exec(select(Message).where(Message.case_id == case_id)).all()
    calls = session.exec(select(Call).where(Call.case_id == case_id)).all()
    contacts = session.exec(select(Contact).where(Contact.case_id == case_id)).all()
    people = session.exec(select(Person).where(Person.case_id == case_id)).all()
    events = session.exec(select(TimelineEvent).where(TimelineEvent.case_id == case_id)).all()

    lines = [
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        f"Evidence files: {len(evidence)} (photos:{sum(1 for e in evidence if e.kind=='photo')}, "
        f"videos:{sum(1 for e in evidence if e.kind=='video')}, "
        f"audio:{sum(1 for e in evidence if e.kind=='audio')})",
        f"Messages: {len(messages)}",
        f"Calls: {len(calls)}",
        f"Contacts: {len(contacts)}",
        f"Persons identified: {len(people)}",
        f"Timeline events: {len(events)}",
        "",
        "--- Contacts ---",
    ]
    for c in contacts[:20]:
        lines.append(f"  {c.phone_number} | {c.name or '(unnamed)'}")

    lines += ["", "--- Sample Messages ---"]
    for m in messages[:30]:
        lines.append(f"  [{m.timestamp}] {m.sender} → {m.recipient}: {m.body[:120]}")

    lines += ["", "--- Timeline Events ---"]
    for e in events[:40]:
        lines.append(f"  [{e.timestamp}] {e.event_type}: {e.summary}")

    lines += ["", "--- Persons ---"]
    for p in people:
        lines.append(f"  Cluster #{p.cluster_key}: {p.label or '(unlabeled)'} — {p.face_count} faces")

    return "\n".join(lines)


def _gateway_generate(case_context: str) -> str:
    g = get_gateway()
    text = g.chat(
        messages=[
            {"role": "system", "content": REPORT_PROMPT},
            {"role": "user", "content": f"Case data:\n{case_context}"},
        ],
        temperature=0.3,
        max_tokens=4096,
    )
    return text


def _template_report(case_context: str) -> str:
    lines = [
        "# Forensic Investigation Report",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        "",
        "## Case Data Summary",
        "",
        "```",
        case_context,
        "```",
        "",
        "## Note",
        "This is an automated summary report. A full investigation report should be produced by a qualified forensic examiner.",
    ]
    return "\n".join(lines)


def generate_report(session: Session, case_id: int) -> str:
    context = _build_case_context(session, case_id)
    if is_available():
        try:
            return _gateway_generate(context)
        except AIGatewayError as exc:
            logger.warning("gateway report generation failed: %s", exc)
    return _template_report(context)


def is_available() -> bool:
    try:
        return get_gateway().is_available()
    except Exception:
        return False
