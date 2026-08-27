from pydantic import BaseModel


class ChainVerificationResponse(BaseModel):
    valid: bool
    total_entries: int
    first_broken_entry_id: int | None = None
    reason: str | None = None
