from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class EvidenceKind(StrEnum):
    photo = "photo"
    video = "video"
    audio = "audio"
    document = "document"
    other = "other"


class EvidenceFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    kind: EvidenceKind
    original_path: str
    file_name: str
    sha256: str = Field(index=True, description="SHA-256 hash computed at ingest time")
    size_bytes: int = 0
    captured_at: datetime | None = Field(default=None, description="EXIF/metadata timestamp if available")
    latitude: float | None = None
    longitude: float | None = None
    deleted_then_recovered: bool = False
    nsfw_score: float | None = Field(default=None, description="0-1 model score; None = not screened yet")
    nsfw_flagged: bool = Field(default=False, description="Flag-for-human-review only, never auto-classified as evidence")
    nsfw_reviewed: bool = Field(default=False, description="Set once a reviewer has manually confirmed/dismissed the flag")
    created_at: datetime = Field(default_factory=utcnow)
