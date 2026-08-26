from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class CallDirection(StrEnum):
    incoming = "incoming"
    outgoing = "outgoing"
    missed = "missed"


class Call(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    number: str
    direction: CallDirection
    duration_seconds: int = 0
    timestamp: datetime = Field(index=True)
