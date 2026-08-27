"""NSFW pre-screening.

Vision AI returns a 0-1 sensitivity score. Score >= 0.7 marks the file for
human review; nothing is auto-classified or auto-deleted (per ForensAI's
explicit human-in-the-loop stance).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlmodel import Session

from app.models.evidence_file import EvidenceFile
from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)

FLAG_THRESHOLD = 0.7

PROMPT = (
    "You are a forensic content sensitivity classifier. Analyze the image and "
    "return a JSON object with two fields: 'score' (float 0-1, where 1 means "
    "explicitly pornographic/CSAM) and 'reason' (short string explaining the rating). "
    "Bias conservative — when in doubt, score lower."
)


def _local_available() -> bool:
    try:
        import opennsfw2  # noqa: F401
        return True
    except ImportError:
        return False


def _local_score(path: str) -> float:
    import opennsfw2

    nsfw_prob, _ = opennsfw2.predict_image(path)
    return float(nsfw_prob)


def _gateway_score(path: str) -> float:
    g = get_gateway()
    try:
        text = g.vision(
            prompt=PROMPT,
            image_path=path,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(text)
        score = float(parsed.get("score", 0.0))
        return max(0.0, min(1.0, score))
    except (AIGatewayError, ValueError, KeyError, TypeError) as exc:
        logger.warning("gateway nsfw score failed: %s", exc)
        return 0.0


def screen_evidence_file(session: Session, evidence_file: EvidenceFile) -> float:
    if not evidence_file.original_path or not Path(evidence_file.original_path).exists():
        return 0.0

    score = 0.0
    if _local_available():
        try:
            score = _local_score(evidence_file.original_path)
        except Exception as exc:
            logger.warning("local nsfw failed: %s — falling back to gateway", exc)
            score = 0.0
    if score == 0.0 and is_available():
        score = _gateway_score(evidence_file.original_path)

    evidence_file.nsfw_score = score
    evidence_file.nsfw_flagged = score >= FLAG_THRESHOLD
    evidence_file.nsfw_reviewed = False
    session.add(evidence_file)
    session.commit()
    return score


def is_available() -> bool:
    if _local_available():
        return True
    try:
        return get_gateway().is_available()
    except Exception:
        return False
