from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    redacted: bool = False
    html_path: str
    pdf_path: str | None = None
    generated_by: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
