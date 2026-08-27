from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class TimelineEventType(StrEnum):
    call = "call"
    message = "message"
    photo = "photo"
    video = "video"
    audio = "audio"
    app_install = "app_install"
    app_uninstall = "app_uninstall"
    file_deleted = "file_deleted"
    file_recovered = "file_recovered"
    anomaly = "anomaly"


class TimelineEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    event_type: TimelineEventType
    timestamp: datetime = Field(index=True)
    summary: str
    source_table: str = Field(description="Name of the table the underlying record lives in")
    source_id: int = Field(description="Primary key of the underlying record")
    latitude: float | None = None
    longitude: float | None = None
