"""Celery app + the case-processing pipeline.

AI tasks (face clustering, transcription) are slow enough that they must not
block the request/response cycle, so they run through Celery. For a
zero-setup demo (no Redis server running) `run_task()` below transparently
falls back to executing the task function inline instead of failing — real
deployments should run `celery -A app.worker worker` against a live broker
so these actually go async.
"""

import logging
import socket
from urllib.parse import urlparse

from celery import Celery
from sqlmodel import Session, select

from app.config import get_settings
from app.database import engine
from app.models.case import Case, CaseStatus
from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.services import anomaly_detection, audit_log, face_recognition, nsfw_screening, semantic_search, transcription
from app.models.transcript import Transcript

logger = logging.getLogger("netsherlock.worker")
settings = get_settings()

celery_app = Celery(
    "netsherlock",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_default_queue = "netsherlock"


def _broker_reachable(url: str, timeout: float = 0.3) -> bool:
    """Fast raw-socket probe for the broker port.

    Skips straight to False on anything unreachable instead of letting
    kombu/Celery's own connection retry logic run -- on a refused
    connection that can take 10s+ (getaddrinfo tries both the IPv4 and
    IPv6 loopback candidates, then several backoff retries), which is
    long enough that an ingest request sitting on it looks hung in the
    browser rather than just falling back to inline execution.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
    except ValueError:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_task(task, *args, **kwargs):
    """Dispatch to Celery; fall back to running inline if the broker is unreachable."""
    if not _broker_reachable(settings.celery_broker_url):
        logger.warning(
            "Celery broker unreachable at %s — running '%s' inline instead", settings.celery_broker_url, task.name
        )
        return task.run(*args, **kwargs)
    try:
        return task.delay(*args, **kwargs)
    except Exception as exc:  # kombu/redis connection errors vary by backend
        logger.warning("Celery broker unavailable (%s) — running '%s' inline instead", exc, task.name)
        return task.run(*args, **kwargs)


@celery_app.task(name="netsherlock.process_case")
def process_case_task(case_id: int) -> dict:
    warnings: list[str] = []
    faces_detected = 0
    people_found = 0
    transcripts_created = 0
    nsfw_screened = 0

    with Session(engine) as session:
        case = session.get(Case, case_id)
        if case is None:
            return {"error": f"case {case_id} not found"}

        evidence_files = session.exec(select(EvidenceFile).where(EvidenceFile.case_id == case_id)).all()

        if face_recognition.is_available():
            for ef in evidence_files:
                if ef.kind == EvidenceKind.photo:
                    faces_detected += face_recognition.process_evidence_file(session, ef)
            people_found = face_recognition.cluster_case(session, case_id)
        else:
            warnings.append("face recognition skipped: torch/facenet-pytorch not installed")

        if transcription.is_available():
            for ef in evidence_files:
                if ef.kind == EvidenceKind.audio:
                    result = transcription.transcribe(ef.original_path)
                    session.add(
                        Transcript(
                            case_id=case_id,
                            evidence_file_id=ef.id,
                            text=result.text,
                            language=result.language,
                        )
                    )
                    transcripts_created += 1
            session.commit()
        else:
            warnings.append("transcription skipped: faster-whisper not installed")

        if nsfw_screening.is_available():
            for ef in evidence_files:
                if ef.kind == EvidenceKind.photo:
                    nsfw_screening.screen_evidence_file(session, ef)
                    nsfw_screened += 1
        else:
            warnings.append("NSFW pre-screening skipped: opennsfw2 not installed")

        if semantic_search.is_available():
            try:
                semantic_search.index_case(session, case_id)
            except semantic_search.ModelUnavailableError as exc:
                warnings.append(str(exc))
        else:
            warnings.append("semantic indexing skipped: sentence-transformers not installed")

        anomalies = anomaly_detection.detect(session, case_id)

        case.status = CaseStatus.ready
        session.add(case)
        session.commit()

        audit_log.append_entry(
            session,
            actor="system",
            action="case.process",
            case_id=case_id,
            payload={
                "faces_detected": faces_detected,
                "people_found": people_found,
                "transcripts_created": transcripts_created,
                "anomalies_found": len(anomalies),
                "nsfw_screened": nsfw_screened,
                "warnings": warnings,
            },
        )

    return {
        "faces_detected": faces_detected,
        "people_found": people_found,
        "transcripts_created": transcripts_created,
        "anomalies_found": len(anomalies),
        "nsfw_screened": nsfw_screened,
        "warnings": warnings,
    }
