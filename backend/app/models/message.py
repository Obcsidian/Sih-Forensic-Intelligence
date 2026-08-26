from datetime import datetime

from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    sender: str
    recipient: str
    body: str = ""
    timestamp: datetime = Field(index=True)
    app: str = Field(default="", description="Messaging app the record came from, e.g. sms/whatsapp")
    embedding_json: str | None = Field(default=None, description="JSON-encoded semantic-search vector")
