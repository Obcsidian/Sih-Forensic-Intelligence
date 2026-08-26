"""Case ingestion adapter.

Real Autopsy parses UFDR/E01 device images and hands off structured evidence.
Standing up that Java/Jython toolchain is out of scope for this demo, so
instead we ingest a **case-export folder** with the shape Autopsy's own
export *would* produce:

    <case_folder>/
        contacts.csv          name,phone_number
        calls.csv             number,direction,duration_seconds,timestamp
        messages.csv          sender,recipient,body,timestamp,app
        device_events.json    [{type, timestamp, detail, file_name?}, ...]
        photos/                *.jpg/*.png (EXIF read for GPS + capture time)
        audio/                 *.wav/*.mp3/*.m4a

`CaseFolderParser` is the only ingestion backend implemented, but it's kept
behind the `UFDRParser` interface below so a real Autopsy/UFDR/E01 parser
can be dropped in later without touching the rest of the pipeline (routers,
DB models, and every AI service key off `EvidenceFile`/`Contact`/`Call`/
`Message` rows, not off the source file format).
"""

import csv
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.models.call import Call, CallDirection
from app.models.case import Case, CaseStatus
from app.models.contact import Contact
from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.models.message import Message
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.services import audit_log

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_exif(path: Path) -> tuple[datetime | None, float | None, float | None]:
    """Best-effort EXIF capture time + GPS extraction. Returns (captured_at, lat, lon)."""
    try:
        from PIL import ExifTags, Image
        from PIL.ExifTags import GPSTAGS
    except ImportError:
        return None, None, None

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None, None, None

            tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            captured_at = None
            if "DateTimeOriginal" in tags or "DateTime" in tags:
                raw = tags.get("DateTimeOriginal") or tags.get("DateTime")
                try:
                    captured_at = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                except (ValueError, TypeError):
                    captured_at = None

            lat = lon = None
            gps_ifd = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else None
            if gps_ifd:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}

                def _to_degrees(value):
                    d, m, s = value
                    return float(d) + float(m) / 60 + float(s) / 3600

                if "GPSLatitude" in gps and "GPSLongitude" in gps:
                    lat = _to_degrees(gps["GPSLatitude"])
                    if gps.get("GPSLatitudeRef") == "S":
                        lat = -lat
                    lon = _to_degrees(gps["GPSLongitude"])
                    if gps.get("GPSLongitudeRef") == "W":
                        lon = -lon

            return captured_at, lat, lon
    except Exception:
        return None, None, None


@dataclass
class IngestSummary:
    contacts: int = 0
    calls: int = 0
    messages: int = 0
    photos: int = 0
    videos: int = 0
    audio_files: int = 0
    device_events: int = 0
    errors: list[str] = field(default_factory=list)


class UFDRParser(ABC):
    """Interface a real Autopsy/UFDR/E01 parser would implement to replace CaseFolderParser."""

    @abstractmethod
    def ingest(self, session: Session, case: Case, source: Path) -> IngestSummary: ...


class CaseFolderParser(UFDRParser):
    def ingest(self, session: Session, case: Case, source: Path) -> IngestSummary:
        summary = IngestSummary()

        self._ingest_contacts(session, case, source, summary)
        self._ingest_calls(session, case, source, summary)
        self._ingest_messages(session, case, source, summary)
        recovered_files = self._ingest_device_events(session, case, source, summary)
        self._ingest_media(session, case, source, summary, recovered_files)

        case.status = CaseStatus.processing
        session.add(case)
        session.commit()

        audit_log.append_entry(
            session,
            actor="system",
            action="ingest.case",
            case_id=case.id,
            payload={"source": str(source), "summary": summary.__dict__},
        )
        return summary

    def _ingest_contacts(self, session, case, source, summary):
        path = source / "contacts.csv"
        if not path.exists():
            return
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                session.add(Contact(case_id=case.id, name=row.get("name", ""), phone_number=row["phone_number"]))
                summary.contacts += 1
        session.commit()

    def _ingest_calls(self, session, case, source, summary):
        path = source / "calls.csv"
        if not path.exists():
            return
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ts = datetime.fromisoformat(row["timestamp"])
                call = Call(
                    case_id=case.id,
                    number=row["number"],
                    direction=CallDirection(row["direction"]),
                    duration_seconds=int(row.get("duration_seconds") or 0),
                    timestamp=ts,
                )
                session.add(call)
                session.flush()
                session.add(
                    TimelineEvent(
                        case_id=case.id,
                        event_type=TimelineEventType.call,
                        timestamp=ts,
                        summary=f"{call.direction.value} call with {call.number} ({call.duration_seconds}s)",
                        source_table="call",
                        source_id=call.id,
                    )
                )
                summary.calls += 1
        session.commit()

    def _ingest_messages(self, session, case, source, summary):
        path = source / "messages.csv"
        if not path.exists():
            return
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ts = datetime.fromisoformat(row["timestamp"])
                msg = Message(
                    case_id=case.id,
                    sender=row["sender"],
                    recipient=row["recipient"],
                    body=row.get("body", ""),
                    timestamp=ts,
                    app=row.get("app", ""),
                )
                session.add(msg)
                session.flush()
                preview = (msg.body[:60] + "...") if len(msg.body) > 60 else msg.body
                session.add(
                    TimelineEvent(
                        case_id=case.id,
                        event_type=TimelineEventType.message,
                        timestamp=ts,
                        summary=f"{msg.sender} -> {msg.recipient}: {preview}",
                        source_table="message",
                        source_id=msg.id,
                    )
                )
                summary.messages += 1
        session.commit()

    def _ingest_device_events(self, session, case, source, summary) -> set[str]:
        path = source / "device_events.json"
        recovered_files: set[str] = set()
        if not path.exists():
            return recovered_files

        events = json.loads(path.read_text(encoding="utf-8"))
        type_map = {
            "app_install": TimelineEventType.app_install,
            "app_uninstall": TimelineEventType.app_uninstall,
            "file_deleted": TimelineEventType.file_deleted,
            "file_recovered": TimelineEventType.file_recovered,
        }
        for event in events:
            event_type = type_map.get(event["type"])
            if event_type is None:
                summary.errors.append(f"unknown device event type: {event['type']}")
                continue
            ts = datetime.fromisoformat(event["timestamp"])
            session.add(
                TimelineEvent(
                    case_id=case.id,
                    event_type=event_type,
                    timestamp=ts,
                    summary=event.get("detail", event["type"]),
                    source_table="device_event",
                    source_id=0,
                )
            )
            if event_type == TimelineEventType.file_recovered and event.get("file_name"):
                recovered_files.add(event["file_name"])
            summary.device_events += 1
        session.commit()
        return recovered_files

    def _ingest_media(self, session, case, source, summary, recovered_files: set[str]):
        for subdir, kinds in ((source / "photos", (PHOTO_EXTENSIONS, EvidenceKind.photo)), (source / "audio", (AUDIO_EXTENSIONS, EvidenceKind.audio))):
            if not subdir.exists():
                continue
            extensions, kind = kinds
            for file_path in sorted(subdir.iterdir()):
                if not file_path.is_file() or file_path.suffix.lower() not in extensions:
                    continue
                captured_at = lat = lon = None
                if kind == EvidenceKind.photo:
                    captured_at, lat, lon = _read_exif(file_path)

                evidence = EvidenceFile(
                    case_id=case.id,
                    kind=kind,
                    original_path=str(file_path),
                    file_name=file_path.name,
                    sha256=sha256_of_file(file_path),
                    size_bytes=file_path.stat().st_size,
                    captured_at=captured_at,
                    latitude=lat,
                    longitude=lon,
                    deleted_then_recovered=file_path.name in recovered_files,
                )
                session.add(evidence)
                session.flush()

                event_type = TimelineEventType.photo if kind == EvidenceKind.photo else TimelineEventType.audio
                session.add(
                    TimelineEvent(
                        case_id=case.id,
                        event_type=event_type,
                        timestamp=captured_at or evidence.created_at,
                        summary=f"{kind.value} evidence ingested: {evidence.file_name}",
                        source_table="evidencefile",
                        source_id=evidence.id,
                        latitude=lat,
                        longitude=lon,
                    )
                )

                if kind == EvidenceKind.photo:
                    summary.photos += 1
                else:
                    summary.audio_files += 1

                audit_log.append_entry(
                    session,
                    actor="system",
                    action="ingest.file",
                    case_id=case.id,
                    payload={"file_name": evidence.file_name, "sha256": evidence.sha256, "kind": kind.value},
                )
        session.commit()
