from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class AuditLogEntry(SQLModel, table=True):
    """Append-only, hash-chained log. Each row commits to the previous row's hash,
    so any edit/delete/reorder of a past entry breaks verify_chain()."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int | None = Field(default=None, foreign_key="case.id", index=True)
    actor: str = Field(description="Username or 'system'")
    action: str = Field(description="Short action code, e.g. 'ingest.file', 'face.cluster'")
    payload_json: str = Field(default="{}")
    timestamp: datetime = Field(default_factory=utcnow)
    prev_hash: str = Field(description="Hash of the previous entry; '0' * 64 for the first entry")
    hash: str = Field(index=True, description="sha256(prev_hash + actor + action + payload_json + timestamp)")
