"""Parses .eml (RFC 822) email files into a normalized message shape.

Uses only the Python standard library (`email` module) -- no extra
dependency needed, unlike photo/audio parsing which leans on Pillow/EXIF.
Mirrors what Autopsy's Email Parser ingest module does: pull structured
sender/recipients/subject/body/date out of a raw email file so it can be
treated as a Message row instead of just an opaque document.
"""

from __future__ import annotations

import email
import email.policy
import email.utils
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedEmail:
    sender: str
    recipients: list[str]
    subject: str
    body: str
    sent_at: datetime | None


def _split_addresses(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [addr for _, addr in email.utils.getaddresses([raw]) if addr]


def parse_eml(content: bytes) -> ParsedEmail | None:
    """Best-effort .eml parse. Returns None if the content has no usable
    'From' header -- caller falls back to treating it as an opaque document,
    same as any other unparsed file."""
    try:
        msg = email.message_from_bytes(content, policy=email.policy.default)
    except Exception:
        return None

    sender_raw = msg.get("From")
    if not sender_raw:
        return None

    sender_list = _split_addresses(sender_raw)
    sender = sender_list[0] if sender_list else str(sender_raw).strip()

    recipients = _split_addresses(msg.get("To")) + _split_addresses(msg.get("Cc"))

    subject = str(msg.get("Subject") or "").strip()

    body = ""
    try:
        body_part = msg.get_body(preferencelist=("plain", "html"))
        if body_part is not None:
            content_text = body_part.get_content()
            body = content_text if isinstance(content_text, str) else content_text.decode("utf-8", errors="replace")
    except Exception:
        body = ""
    body = (body or "").strip()

    sent_at = None
    date_raw = msg.get("Date")
    if date_raw:
        try:
            parsed = email.utils.parsedate_to_datetime(str(date_raw))
            sent_at = parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
        except (TypeError, ValueError):
            sent_at = None

    return ParsedEmail(sender=sender, recipients=recipients, subject=subject, body=body, sent_at=sent_at)


def format_message_body(parsed: ParsedEmail) -> str:
    return f"Subject: {parsed.subject}\n\n{parsed.body}" if parsed.subject else parsed.body
