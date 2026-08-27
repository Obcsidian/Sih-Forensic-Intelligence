from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class FaceDetection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    evidence_file_id: int = Field(foreign_key="evidencefile.id", index=True)
    person_id: int | None = Field(default=None, foreign_key="person.id", index=True)
    box_x: float
    box_y: float
    box_w: float
    box_h: float
    embedding_json: str = Field(description="JSON-encoded float vector from the embedding model")
    detection_confidence: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)
