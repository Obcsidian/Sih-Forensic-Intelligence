from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


class SearchHitResponse(BaseModel):
    source_type: str
    source_id: int
    text: str
    score: float
