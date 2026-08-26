"""Append-only, hash-chained audit log.

Every action (ingest, face clustering, transcription, report export, ...) gets
recorded here. Each entry commits to the hash of the entry before it, so
tampering with (or deleting) any past entry is detectable by re-walking the
chain and recomputing hashes — the same tamper-evidence property Autopsy's
own SHA-256 hashing gives the raw evidence, applied to the AI layer's actions.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.audit_log import AuditLogEntry

GENESIS_HASH = "0" * 64


def _compute_hash(prev_hash: str, actor: str, action: str, payload_json: str, timestamp_iso: str) -> str:
    material = f"{prev_hash}|{actor}|{action}|{payload_json}|{timestamp_iso}".encode()
    return hashlib.sha256(material).hexdigest()


def append_entry(
    session: Session,
    *,
    actor: str,
    action: str,
    payload: dict | None = None,
    case_id: int | None = None,
) -> AuditLogEntry:
    last = session.exec(select(AuditLogEntry).order_by(AuditLogEntry.id.desc())).first()
    prev_hash = last.hash if last else GENESIS_HASH

    entry = AuditLogEntry(
        case_id=case_id,
        actor=actor,
        action=action,
        payload_json=json.dumps(payload or {}, default=str, sort_keys=True),
        prev_hash=prev_hash,
    )
    entry.hash = _compute_hash(prev_hash, entry.actor, entry.action, entry.payload_json, entry.timestamp.isoformat())

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@dataclass
class ChainVerificationResult:
    valid: bool
    total_entries: int
    first_broken_entry_id: int | None = None
    reason: str | None = None


def verify_chain(session: Session) -> ChainVerificationResult:
    entries = session.exec(select(AuditLogEntry).order_by(AuditLogEntry.id.asc())).all()
    expected_prev = GENESIS_HASH

    for entry in entries:
        if entry.prev_hash != expected_prev:
            return ChainVerificationResult(
                valid=False,
                total_entries=len(entries),
                first_broken_entry_id=entry.id,
                reason="prev_hash does not match the hash of the preceding entry",
            )
        recomputed = _compute_hash(
            entry.prev_hash, entry.actor, entry.action, entry.payload_json, entry.timestamp.isoformat()
        )
        if recomputed != entry.hash:
            return ChainVerificationResult(
                valid=False,
                total_entries=len(entries),
                first_broken_entry_id=entry.id,
                reason="stored hash does not match recomputed hash — entry contents were altered",
            )
        expected_prev = entry.hash

    return ChainVerificationResult(valid=True, total_entries=len(entries))
