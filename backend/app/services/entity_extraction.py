"""AI-powered entity extraction from text.

Uses the AI gateway to extract structured entities (names, phone numbers,
addresses, etc.) from messages and transcripts. Falls back to regex-based
extraction when the gateway is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.call import Call
from app.models.contact import Contact
from app.models.message import Message
from app.models.transcript import Transcript
from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = (
    "You are a forensic text-analysis engine. Extract structured entities from the "
    "following text. Return ONLY a valid JSON object with these optional keys:\n"
    "  - names: list of person names mentioned\n"
    "  - phone_numbers: list of phone numbers (with country code if identifiable)\n"
    "  - addresses: list of addresses or locations\n"
    "  - emails: list of email addresses\n"
    "  - dates: list of date/time references\n"
    "  - suspicious: list of suspicious phrases or activities\n"
    "Return ONLY the JSON object, no markdown, no explanation."
)


@dataclass
class ExtractedEntities:
    names: list[str]
    phone_numbers: list[str]
    addresses: list[str]
    emails: list[str]
    dates: list[str]
    suspicious: list[str]


def _regex_extract(text: str) -> ExtractedEntities:
    phone_re = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
    )
    email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    return ExtractedEntities(
        names=[],
        phone_numbers=phone_re.findall(text),
        addresses=[],
        emails=email_re.findall(text),
        dates=[],
        suspicious=[],
    )


def _gateway_extract(texts: list[str]) -> list[ExtractedEntities | None]:
    g = get_gateway()
    combined = "\n---\n".join(texts)
    try:
        text = g.chat(
            messages=[{"role": "user", "content": f"{EXTRACT_PROMPT}\n\nText:\n{combined}"}],
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
        parsed = json.loads(text)
        # Distribute results back to each text roughly
        results: list[ExtractedEntities | None] = []
        base = ExtractedEntities(
            names=parsed.get("names", [])[: len(texts)],
            phone_numbers=parsed.get("phone_numbers", [])[: len(texts)],
            addresses=parsed.get("addresses", [])[: len(texts)],
            emails=parsed.get("emails", [])[: len(texts)],
            dates=parsed.get("dates", [])[: len(texts)],
            suspicious=parsed.get("suspicious", [])[: len(texts)],
        )
        for _ in texts:
            results.append(base)
        return results
    except (AIGatewayError, ValueError, KeyError) as exc:
        logger.warning("gateway entity extract failed: %s", exc)
        return [None] * len(texts)


def extract_from_text(texts: list[str]) -> list[ExtractedEntities]:
    if not texts:
        return []
    if is_available():
        results = _gateway_extract(texts)
        return [r if r else _regex_extract(t) for r, t in zip(results, texts)]
    return [_regex_extract(t) for t in texts]


def enrich_case(session: Session, case_id: int) -> dict:
    """Extract and store entities from all messages and transcripts."""
    messages = session.exec(select(Message).where(Message.case_id == case_id)).all()
    transcripts = session.exec(select(Transcript).where(Transcript.case_id == case_id)).all()

    text_bodies = [m.body for m in messages] + [t.text for t in transcripts]
    entities = extract_from_text(text_bodies)

    msg_entities = entities[: len(messages)]
    trn_entities = entities[len(messages) :]

    # Collect unique phone numbers → create/update contacts
    seen_phones: set[str] = set()
    for msg, ent in zip(messages, msg_entities):
        for ph in ent.phone_numbers:
            ph_clean = re.sub(r"[^\d+]", "", ph)
            if len(ph_clean) >= 7 and ph_clean not in seen_phones:
                seen_phones.add(ph_clean)
                existing = session.exec(
                    select(Contact).where(
                        Contact.case_id == case_id, Contact.phone_number == ph_clean
                    )
                ).first()
                if not existing:
                    session.add(
                        Contact(case_id=case_id, phone_number=ph_clean, name=ent.names[0] if ent.names else "")
                    )

    session.commit()
    return {"entities_extracted": len(seen_phones)}


def is_available() -> bool:
    try:
        return get_gateway().is_available()
    except Exception:
        return False
