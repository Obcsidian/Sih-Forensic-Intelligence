from pydantic import BaseModel


class GraphNodeResponse(BaseModel):
    id: str
    label: str
    call_count: int
    message_count: int


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    weight: int


class GraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
