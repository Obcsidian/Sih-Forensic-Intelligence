from pydantic import BaseModel


class GenerateReportRequest(BaseModel):
    redacted: bool = False


class TTSRequest(BaseModel):
    text: str
