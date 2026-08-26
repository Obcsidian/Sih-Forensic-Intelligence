"""Rule-based anomaly detection over ingested case data.

No ML model needed for these — they're straightforward pattern checks over
timeline data, matching the README's examples (deleted-then-recovered files,
briefly installed apps) plus an odd-hour-activity heuristic. Each hit is
recorded as its own TimelineEvent(type=anomaly) so it surfaces directly in
the timeline view.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models.evidence_file import EvidenceFile
from app.models.timeline_event import TimelineEvent, TimelineEventType

SHORT_INSTALL_WINDOW = timedelta(hours=24)
ODD_HOURS = range(2, 5)  # 02:00-04:59 local-to-device-clock


@dataclass
class Anomaly:
    kind: str
    summary: str
    timestamp: datetime


def detect(session: Session, case_id: int) -> list[Anomaly]:
    # Idempotent: wipe previously-recorded anomaly events for this case before re-detecting,
    # so calling this more than once doesn't duplicate timeline entries.
    existing = session.exec(
        select(TimelineEvent).where(
            TimelineEvent.case_id == case_id, TimelineEvent.event_type == TimelineEventType.anomaly
        )
    ).all()
    for event in existing:
        session.delete(event)
    session.commit()

    anomalies: list[Anomaly] = []
    anomalies += _deleted_then_recovered(session, case_id)
    anomalies += _briefly_installed_apps(session, case_id)
    anomalies += _odd_hour_activity(session, case_id)

    for anomaly in anomalies:
        session.add(
            TimelineEvent(
                case_id=case_id,
                event_type=TimelineEventType.anomaly,
                timestamp=anomaly.timestamp,
                summary=f"[{anomaly.kind}] {anomaly.summary}",
                source_table="anomaly",
                source_id=0,
            )
        )
    session.commit()
    return anomalies


def _deleted_then_recovered(session: Session, case_id: int) -> list[Anomaly]:
    files = session.exec(
        select(EvidenceFile).where(
            EvidenceFile.case_id == case_id, EvidenceFile.deleted_then_recovered.is_(True)
        )
    ).all()
    return [
        Anomaly(
            kind="deleted_then_recovered",
            summary=f"'{f.file_name}' was deleted and later recovered from the device",
            timestamp=f.captured_at or f.created_at,
        )
        for f in files
    ]


def _briefly_installed_apps(session: Session, case_id: int) -> list[Anomaly]:
    events = session.exec(
        select(TimelineEvent)
        .where(
            TimelineEvent.case_id == case_id,
            TimelineEvent.event_type.in_([TimelineEventType.app_install, TimelineEventType.app_uninstall]),
        )
        .order_by(TimelineEvent.timestamp.asc())
    ).all()

    installs: dict[str, TimelineEvent] = {}
    hits: list[Anomaly] = []
    for event in events:
        app_name = event.summary
        if event.event_type == TimelineEventType.app_install:
            installs[app_name] = event
        elif event.event_type == TimelineEventType.app_uninstall and app_name in installs:
            install_event = installs.pop(app_name)
            if event.timestamp - install_event.timestamp <= SHORT_INSTALL_WINDOW:
                hits.append(
                    Anomaly(
                        kind="briefly_installed_app",
                        summary=f"'{app_name}' was installed and removed within "
                        f"{(event.timestamp - install_event.timestamp)}",
                        timestamp=event.timestamp,
                    )
                )
    return hits


def _odd_hour_activity(session: Session, case_id: int) -> list[Anomaly]:
    events = session.exec(
        select(TimelineEvent).where(
            TimelineEvent.case_id == case_id,
            TimelineEvent.event_type.in_([TimelineEventType.call, TimelineEventType.message]),
        )
    ).all()
    return [
        Anomaly(
            kind="odd_hour_activity",
            summary=f"Activity at {event.timestamp.strftime('%H:%M')}: {event.summary}",
            timestamp=event.timestamp,
        )
        for event in events
        if event.timestamp.hour in ODD_HOURS
    ]
