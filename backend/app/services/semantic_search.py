"""Embedding-based semantic search over transcripts and messages.

Embeds with sentence-transformers (all-MiniLM-L6-v2) and searches with a
FAISS flat inner-product index built on the fly from the case's stored
embeddings — the case-scale data this demo targets (hundreds to low
thousands of transcripts/messages) makes a persistent index unnecessary.
"""

import json
from dataclasses import dataclass
from functools import lru_cache

from sqlmodel import Session, select

from app.models.message import Message
from app.models.transcript import Transcript


class ModelUnavailableError(RuntimeError):
    pass


@lru_cache
def _get_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ModelUnavailableError(
            "Semantic search requires 'sentence-transformers' — "
            "install backend/requirements.txt to enable this feature."
        ) from exc
    return SentenceTransformer("all-MiniLM-L6-v2")


def is_available() -> bool:
    try:
        _get_model()
        return True
    except ModelUnavailableError:
        return False


def embed_texts(texts: list[str]):
    import numpy as np

    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.asarray(vectors, dtype="float32")


def index_case(session: Session, case_id: int) -> int:
    """Compute + store embeddings for any transcript/message in the case that doesn't have one yet."""
    transcripts = session.exec(
        select(Transcript).where(Transcript.case_id == case_id, Transcript.embedding_json.is_(None))
    ).all()
    messages = session.exec(
        select(Message).where(Message.case_id == case_id, Message.embedding_json.is_(None))
    ).all()

    targets = [t for t in transcripts if t.text.strip()] + [m for m in messages if m.body.strip()]
    if not targets:
        return 0

    texts = [t.text if isinstance(t, Transcript) else t.body for t in targets]
    vectors = embed_texts(texts)

    for record, vector in zip(targets, vectors, strict=True):
        record.embedding_json = json.dumps(vector.tolist())
        session.add(record)
    session.commit()
    return len(targets)


@dataclass
class SearchHit:
    source_type: str  # "transcript" | "message"
    source_id: int
    text: str
    score: float


def search(session: Session, case_id: int, query: str, top_k: int = 10) -> list[SearchHit]:
    import numpy as np

    try:
        import faiss
    except ImportError as exc:
        raise ModelUnavailableError(
            "Semantic search requires 'faiss-cpu' — install backend/requirements.txt to enable this feature."
        ) from exc

    transcripts = session.exec(
        select(Transcript).where(Transcript.case_id == case_id, Transcript.embedding_json.is_not(None))
    ).all()
    messages = session.exec(
        select(Message).where(Message.case_id == case_id, Message.embedding_json.is_not(None))
    ).all()

    records = [("transcript", t.id, t.text, t.embedding_json) for t in transcripts]
    records += [("message", m.id, m.body, m.embedding_json) for m in messages]
    if not records:
        return []

    vectors = np.array([json.loads(r[3]) for r in records], dtype="float32")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    query_vector = embed_texts([query])
    scores, indices = index.search(query_vector, min(top_k, len(records)))

    hits = []
    for score, idx in zip(scores[0], indices[0], strict=True):
        if idx == -1:
            continue
        source_type, source_id, text, _ = records[idx]
        hits.append(SearchHit(source_type=source_type, source_id=source_id, text=text, score=float(score)))
    return hits
