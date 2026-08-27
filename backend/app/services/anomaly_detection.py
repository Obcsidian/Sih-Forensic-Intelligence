"""Anomaly detection using AI reasoning.

Uses the AI gateway's chat model to analyze patterns and flag anomalies
in timeline events, deleted-recovered files, and unusual activity sequences.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.evidence_file import EvidenceFile
from app.models.timeline_event import TimelineEvent
from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)

ANOMALY_PROMPT = (
    "You are a forensic anomaly-detection system. Analyze the following timeline of events "
    "from a digital investigation. Return a JSON object with a single key 'anomalies' "
    "containing a list of anomaly descriptions (strings). Each anomaly should describe:\n"
    "  - What is unusual or suspicious\n"
    "  - Why it stands out\n"
    "  - Recommended follow-up action\n"
    "Return ONLY the JSON object, no markdown, no explanation.\n\n"
    "Timeline events (format: TYPE | TIMESTAMP | SUMMARY):\n{events}\n"
)


@dataclass
class Anomaly:
    timestamp: str
    event_type: str
    summary: str
    severity: str  # low, medium, high
    description: str
    recommendation: str


def _detect_anomalies_from_events(
    events: list[TimelineEvent],
) -> list[Anomaly]:
    if len(events) < 3:
        return []

    lines = [f"{e.event_type} | {e.timestamp} | {e.summary}" for e in events]
    events_block = "\n".join(lines[:200])  # cap at 200 events

    g = get_gateway()
    try:
        text = g.chat(
            messages=[
                {
                    "role": "user",
                    "content": ANOMALY_PROMPT.format(events=events_block),
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1536,
        )
        parsed = json.loads(text)
        anomalies = parsed.get("anomalies", [])
        return [
            Anomaly(
                timestamp=events[min(i, len(events) - 1)].timestamp,
                event_type="anomaly",
                summary=a.get("summary", a) if isinstance(a, dict) else str(a),
                severity=a.get("severity", "medium") if isinstance(a, dict) else "medium",
                description=a.get("description", "") if isinstance(a, dict) else "",
                recommendation=a.get("recommendation", "") if isinstance(a, dict) else "",
            )
            for i, a in enumerate(anomalies[:20])  # cap at 20
        ]
    except (AIGatewayError, ValueError, KeyError) as exc:
        logger.warning("gateway anomaly detection failed: %s", exc)
        return []


def detect_case_anomalies(session: Session, case_id: int) -> list[Anomaly]:
    events = session.exec(
        select(TimelineEvent)
        .where(TimelineEvent.case_id == case_id)
        .order_by(TimelineEvent.timestamp)
    ).all()

    # Always flag clear-cut anomalies first
    anomalies: list[Anomaly] = []

    # 1. Deleted-then-recovered files
    deleted_recovered = session.exec(
        select(EvidenceFile).where(
            EvidenceFile.case_id == case_id, EvidenceFile.deleted_then_recovered == True
        )
    ).all()
    for ev in deleted_recovered:
        anomalies.append(
            Anomaly(
                timestamp=ev.created_at,
                event_type="anomaly",
                summary=f"File '{ev.file_name}' was deleted then recovered",
                severity="high",
                description=f"File {ev.sha256[:16]}... was deleted and then recovered from device storage.",
                recommendation="Verify this file was not intentionally hidden or tampered with.",
            )
        )

    # 2. Briefly installed apps (app_install followed quickly by app_uninstall)
    install_map: dict[str, TimelineEvent] = {}
    uninstall_set: set[str] = set()
    for e in events:
        if e.event_type == "app_install":
            install_map[e.summary] = e
        elif e.event_type == "app_uninstall":
            uninstall_set.add(e.summary)
    for summary in uninstall_set:
        if summary in install_map:
            install_ev = install_map[summary]
            anomalies.append(
                Anomaly(
                    timestamp=install_ev.timestamp,
                    event_type="anomaly",
                    summary=f"App briefly installed then uninstalled: {summary}",
                    severity="medium",
                    description=f"App '{summary}' was installed and uninstalled in the same session.",
                    recommendation="Investigate whether this app was used for any communication.",
                )
            )

    # 3. AI-powered deeper analysis
    if is_available() and len(events) >= 5:
        try:
            ai_anomalies = _detect_anomalies_from_events(events)
            anomalies.extend(ai_anomalies)
        except Exception as exc:
            logger.warning("AI anomaly detection failed: %s", exc)

    # De-duplicate by summary
    seen = set()
    deduped: list[Anomaly] = []
    for a in anomalies:
        key = a.summary[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    return deduped


def is_available() -> bool:
    try:
        return get_gateway().is_available()
    except Exception:
        return False
