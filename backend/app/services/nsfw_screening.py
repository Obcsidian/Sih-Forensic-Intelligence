"""NSFW/CSAM pre-screening — flag-for-human-review ONLY.

Per the README's Limitations section: this never auto-classifies content as
evidence and never auto-deletes anything. It sets EvidenceFile.nsfw_flagged
so a reviewer can prioritize it; EvidenceFile.nsfw_reviewed must be set
explicitly by a reviewer/investigator via the API before the flag is
considered resolved.
"""

from functools import lru_cache

from sqlmodel import Session

from app.models.evidence_file import EvidenceFile

FLAG_THRESHOLD = 0.7


class ModelUnavailableError(RuntimeError):
    pass


@lru_cache
def _get_model():
    try:
        import opennsfw2  # noqa: F401
    except ImportError as exc:
        raise ModelUnavailableError(
            "NSFW pre-screening requires 'opennsfw2' — install backend/requirements.txt to enable this feature."
        ) from exc
    return opennsfw2


def is_available() -> bool:
    try:
        _get_model()
        return True
    except ModelUnavailableError:
        return False


def screen_evidence_file(session: Session, evidence_file: EvidenceFile) -> float:
    opennsfw2 = _get_model()
    score = float(opennsfw2.predict_image(evidence_file.original_path))

    evidence_file.nsfw_score = score
    evidence_file.nsfw_flagged = score >= FLAG_THRESHOLD
    evidence_file.nsfw_reviewed = False
    session.add(evidence_file)
    session.commit()
    return score
