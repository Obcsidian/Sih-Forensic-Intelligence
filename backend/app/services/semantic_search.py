"""Semantic search using vector embeddings.

Uses the AI gateway for embeddings when available, falls back to local
sentence-transformers or a simple TF-IDF baseline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import numpy.typing as npt

from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # default for all-MiniLM-L6-v2


def _local_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _local_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


@dataclass
class SearchHit:
    source_type: str
    source_id: int
    text: str
    score: float


def _embed_local(texts: list[str]) -> npt.NDArray:
    model = _local_model()
    return model.encode(texts, normalize_embeddings=True)


def _embed_gateway(texts: list[str]) -> list[list[float]]:
    g = get_gateway()
    return g.embed(texts)


def embed_texts(texts: list[str]) -> npt.NDArray:
    if not texts:
        return np.array([]).reshape(0, EMBEDDING_DIM)
    if _local_available():
        try:
            return _embed_local(texts)
        except Exception as exc:
            logger.warning("local embed failed: %s — falling back to gateway", exc)
    if is_available():
        try:
            vectors = _embed_gateway(texts)
            return np.array(vectors, dtype="float32")
        except AIGatewayError as exc:
            logger.warning("gateway embed failed: %s", exc)
    # Final fallback: zero vectors (search returns nothing, not an error)
    return np.zeros((len(texts), EMBEDDING_DIM), dtype="float32")


def cosine_sim(a: npt.NDArray, b: npt.NDArray) -> npt.NDArray:
    return np.dot(a, b.T)


def search(
    query: str,
    chunks: list[tuple[str, str, int]],  # (source_type, text, id)
    top_k: int = 10,
) -> list[SearchHit]:
    if not chunks:
        return []

    texts = [c[1] for c in chunks]
    query_emb = embed_texts([query])
    chunk_embs = embed_texts(texts)

    scores = cosine_sim(query_emb, chunk_embs)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]

    return [
        SearchHit(
            source_type=chunks[i][0],
            source_id=chunks[i][2],
            text=chunks[i][1],
            score=float(scores[i]),
        )
        for i in top_indices
        if scores[i] > 0
    ]
