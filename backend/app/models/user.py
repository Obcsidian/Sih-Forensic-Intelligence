from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class Role(StrEnum):
    investigator = "investigator"
    reviewer = "reviewer"
    read_only = "read_only"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    role: Role = Field(default=Role.read_only)
    full_name: str = ""
    created_at: datetime = Field(default_factory=utcnow)
