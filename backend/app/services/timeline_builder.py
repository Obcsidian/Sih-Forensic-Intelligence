"""Timeline read access.

TimelineEvent rows are written directly at ingest time (calls, messages,
photos/audio with EXIF/GPS, device events) and at anomaly-detection time —
this module just provides the merged, sorted read path the API/frontend use.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.models.timeline_event import TimelineEvent, TimelineEventType


def get_timeline(
    session: Session,
    case_id: int,
    event_types: list[TimelineEventType] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[TimelineEvent]:
    query = select(TimelineEvent).where(TimelineEvent.case_id == case_id)
    if event_types:
        query = query.where(TimelineEvent.event_type.in_(event_types))
    if start:
        query = query.where(TimelineEvent.timestamp >= start)
    if end:
        query = query.where(TimelineEvent.timestamp <= end)
    query = query.order_by(TimelineEvent.timestamp.asc())
    return session.exec(query).all()
