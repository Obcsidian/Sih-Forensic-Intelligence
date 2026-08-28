from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class RegistryArtifactKind(StrEnum):
    installed_program = "installed_program"
    autorun_entry = "autorun_entry"
    recent_document = "recent_document"
    os_info = "os_info"
    network_connection = "network_connection"


class RegistryArtifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    data_source_id: int | None = Field(default=None, foreign_key="datasource.id", index=True)
    evidence_file_id: int | None = Field(default=None, foreign_key="evidencefile.id", index=True)
    kind: RegistryArtifactKind = Field(index=True)
    hive: str = Field(description="SOFTWARE / SYSTEM / NTUSER.DAT")
    owner: str | None = Field(default=None, description="Username, derived from path, for per-user (NTUSER.DAT) hives")
    key_path: str = ""
    name: str = ""
    value: str = ""
    raw_json: str = Field(default="", description="Full parsed entry as JSON, for a details view")
    timestamp: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)
