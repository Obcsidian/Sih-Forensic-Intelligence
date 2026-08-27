from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class Transcript(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    evidence_file_id: int = Field(foreign_key="evidencefile.id", index=True, unique=True)
    text: str = ""
    language: str = ""
    embedding_json: str | None = Field(default=None, description="JSON-encoded semantic-search vector")
    created_at: datetime = Field(default_factory=utcnow)
