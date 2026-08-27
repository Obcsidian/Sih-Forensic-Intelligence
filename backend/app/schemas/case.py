from pydantic import BaseModel


class CaseCreateRequest(BaseModel):
    name: str
    description: str = ""
    source_path: str


class IngestSummaryResponse(BaseModel):
    contacts: int
    calls: int
    messages: int
    photos: int
    videos: int
    audio_files: int
    device_events: int
    errors: list[str]


class ProcessCaseResponse(BaseModel):
    faces_detected: int
    people_found: int
    transcripts_created: int
    anomalies_found: int
    nsfw_screened: int
    warnings: list[str]
