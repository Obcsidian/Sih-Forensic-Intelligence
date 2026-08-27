from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class Person(SQLModel, table=True):
    """A face cluster: one row per distinct person InsightFace/facenet found across the case."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    label: str = Field(default="", description="Investigator-assigned name/label, blank until reviewed")
    cluster_key: int = Field(description="Raw cluster id from the clustering algorithm (-1 = unclustered/noise)")
    representative_face_id: int | None = Field(default=None, foreign_key="facedetection.id")
    face_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
