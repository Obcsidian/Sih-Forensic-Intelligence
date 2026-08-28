from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class DataSourceStatus(StrEnum):
    created = "created"
    ingesting = "ingesting"
    ready = "ready"
    failed = "failed"


class DataSource(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    name: str
    source_path: str = Field(description="Path to the E01/UFDR/segment-set that was ingested")
    status: DataSourceStatus = Field(default=DataSourceStatus.created)
    error: str | None = Field(default=None, description="Ingest error/warning summary, if status is failed")
    created_by: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
