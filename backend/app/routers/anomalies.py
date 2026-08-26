from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.models.user import User
from app.security import require_any_role, require_investigator
from app.services import anomaly_detection, audit_log

router = APIRouter(prefix="/cases/{case_id}/anomalies", tags=["anomalies"])


@router.get("", response_model=list[TimelineEvent])
def list_anomalies(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[TimelineEvent]:
    return session.exec(
        select(TimelineEvent)
        .where(TimelineEvent.case_id == case_id, TimelineEvent.event_type == TimelineEventType.anomaly)
        .order_by(TimelineEvent.timestamp.asc())
    ).all()


@router.post("/recompute", response_model=list[TimelineEvent])
def recompute_anomalies(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
) -> list[TimelineEvent]:
    anomaly_detection.detect(session, case_id)
    audit_log.append_entry(session, actor=user.username, action="anomaly.recompute", case_id=case_id)
    return session.exec(
        select(TimelineEvent)
        .where(TimelineEvent.case_id == case_id, TimelineEvent.event_type == TimelineEventType.anomaly)
        .order_by(TimelineEvent.timestamp.asc())
    ).all()
