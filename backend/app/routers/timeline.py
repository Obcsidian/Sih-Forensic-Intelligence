from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.models.user import User
from app.security import require_any_role
from app.services import timeline_builder

router = APIRouter(prefix="/cases/{case_id}/timeline", tags=["timeline"])


@router.get("", response_model=list[TimelineEvent])
def get_timeline(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
    event_type: list[TimelineEventType] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[TimelineEvent]:
    return timeline_builder.get_timeline(session, case_id, event_types=event_type, start=start, end=end)
