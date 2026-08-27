from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class CaseStatus(StrEnum):
    created = "created"
    ingesting = "ingesting"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Case(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    source_path: str = Field(description="Path to the case-export folder that was ingested")
    status: CaseStatus = Field(default=CaseStatus.created)
    created_by: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
