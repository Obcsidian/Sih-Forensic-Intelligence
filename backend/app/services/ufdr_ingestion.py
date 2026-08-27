"""UFDR (Cellebrite Physical/Logical Analyzer export) ingestion adapter.

A .ufdr file is a ZIP archive. Cellebrite's own internal format isn't
publicly documented, but the widely-used interop shape (the one every
third-party UFDR reader targets) is a `report.xml` (commonly under
`Reports/report.xml` or at the archive root) containing a flat list of
<model type="..."> records -- Contact, Call, SMS/Chat, Image/Video/Audio,
etc. -- each with <field name="..."><value>...</value></field> children,
plus the referenced media files sitting alongside it in the archive.

Field names and exactly which model types appear vary by Cellebrite
version/extraction, so this parser is intentionally tolerant: it matches
field names against alias lists rather than exact strings, and any model
type or record it can't confidently map is reported in
IngestSummary.errors (with a count) instead of silently dropped or
guessed at. It has not been validated against a real Cellebrite export --
only against a hand-built synthetic fixture matching the documented
shape -- so treat first results as something to sanity-check, and note
down any transformations here that need to change so we can extend the
alias lists.
"""

import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from sqlmodel import Session

from app.config import get_settings
from app.models.call import Call, CallDirection
from app.models.case import Case
from app.models.contact import Contact
from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.models.message import Message
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.services import audit_log
from app.services.ingestion import IngestSummary, UFDRParser, _read_exif, sha256_of_file

UFDR_EXTENSIONS = {".ufdr", ".ufd"}

CONTACT_TYPES = {"contact", "contacts"}
CALL_TYPES = {"call", "calls"}
MESSAGE_TYPES = {"sms", "mms", "chat", "chatmessage", "instantmessage", "message", "im"}
MEDIA_TYPES = {"image", "video", "audio", "multimediafile", "file", "picture", "photo"}

NAME_FIELDS = {"name", "contact name", "displayname"}
PHONE_FIELDS = {"phone", "phone number", "number", "identifier"}
TIMESTAMP_FIELDS = {"timestamp", "time", "date", "time stamp", "start time"}
DIRECTION_FIELDS = {"direction", "call type"}
DURATION_FIELDS = {"duration", "duration (seconds)", "call duration"}
BODY_FIELDS = {"body", "text", "message", "content"}
FROM_FIELDS = {"from", "sender", "source"}
TO_FIELDS = {"to", "recipient", "destination", "party"}
SOURCE_APP_FIELDS = {"source", "app", "source application", "network", "service"}
FILENAME_FIELDS = {"filename", "file name"}
PATH_FIELDS = {"local path", "path", "file path", "source file"}

MAX_EXTRACT_BYTES = 200 * 1024 * 1024


def is_available() -> bool:
    return True


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _field_dict(model_el) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field_el in model_el:
        if _strip_ns(field_el.tag).lower() != "field":
            continue
        name = (field_el.get("name") or field_el.get("Name") or "").strip().lower()
        if not name:
            continue
        value_el = None
        for child in field_el:
            if _strip_ns(child.tag).lower() == "value":
                value_el = child
                break
        text = (value_el.text if value_el is not None else field_el.text) or ""
        fields[name] = text.strip()
    return fields


def _get(fields: dict[str, str], aliases: set[str]) -> str | None:
    for alias in aliases:
        if alias in fields and fields[alias]:
            return fields[alias]
    return None


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    cleaned = raw.strip()
    paren = cleaned.find("(")
    if paren != -1:
        cleaned = cleaned[:paren].strip()
    for candidate in (cleaned, cleaned.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _find_report_xml(zf: zipfile.ZipFile) -> str | None:
    candidates = [n for n in zf.namelist() if n.lower().endswith("report.xml")]
    if candidates:
        candidates.sort(key=len)
        return candidates[0]
    for n in zf.namelist():
        if n.lower().endswith(".xml"):
            return n
    return None


class CellebriteUFDRParser(UFDRParser):
    def ingest(self, session: Session, case: Case, source: Path) -> IngestSummary:
        summary = IngestSummary()

        try:
            zf = zipfile.ZipFile(source)
        except zipfile.BadZipFile as exc:
            summary.errors.append(f"'{source}' is not a valid UFDR/ZIP archive: {exc}")
            return summary

        with zf:
            report_name = _find_report_xml(zf)
            if report_name is None:
                summary.errors.append("no report.xml found inside the UFDR archive; nothing ingested")
                return summary

            try:
                root = ElementTree.fromstring(zf.read(report_name))
            except ElementTree.ParseError as exc:
                summary.errors.append(f"failed to parse {report_name}: {exc}")
                return summary

            extract_dir = get_settings().storage_path / "extracted" / f"case_{case.id}"
            extract_dir.mkdir(parents=True, exist_ok=True)

            unhandled: dict[str, int] = {}
            seen_names: set[str] = set()

            for model_el in root.iter():
                if _strip_ns(model_el.tag).lower() != "model":
                    continue
                raw_type = (model_el.get("type") or model_el.get("Type") or "").strip()
                model_type = raw_type.lower()
                if not model_type:
                    continue
                fields = _field_dict(model_el)

                if model_type in CONTACT_TYPES:
                    self._ingest_contact(session, case, fields, summary)
                elif model_type in CALL_TYPES:
                    self._ingest_call(session, case, fields, summary)
                elif model_type in MESSAGE_TYPES:
                    self._ingest_message(session, case, fields, summary)
                elif model_type in MEDIA_TYPES:
                    self._ingest_media(session, case, fields, zf, extract_dir, summary, seen_names)
                else:
                    unhandled[raw_type] = unhandled.get(raw_type, 0) + 1

            for model_type, count in unhandled.items():
                summary.errors.append(f"unhandled UFDR model type '{model_type}' ({count} record(s)) skipped")

        session.commit()
        audit_log.append_entry(
            session,
            actor="system",
            action="ingest.case",
            case_id=case.id,
            payload={"source": str(source), "summary": summary.__dict__},
        )
        return summary

    def _ingest_contact(self, session, case, fields, summary):
        phone = _get(fields, PHONE_FIELDS)
        if not phone:
            summary.errors.append("skipped a Contact record with no phone/identifier field")
            return
        session.add(Contact(case_id=case.id, name=_get(fields, NAME_FIELDS) or "", phone_number=phone))
        summary.contacts += 1

    def _ingest_call(self, session, case, fields, summary):
        ts = _parse_timestamp(_get(fields, TIMESTAMP_FIELDS))
        number = _get(fields, PHONE_FIELDS)
        if ts is None or not number:
            summary.errors.append("skipped a Call record with missing/unparseable timestamp or number")
            return

        raw_direction = (_get(fields, DIRECTION_FIELDS) or "").lower()
        direction = CallDirection.outgoing if "out" in raw_direction else CallDirection.incoming

        duration_raw = _get(fields, DURATION_FIELDS)
        try:
            duration = int(float(duration_raw)) if duration_raw else 0
        except ValueError:
            duration = 0

        call = Call(case_id=case.id, number=number, direction=direction, duration_seconds=duration, timestamp=ts)
        session.add(call)
        session.flush()
        session.add(
            TimelineEvent(
                case_id=case.id,
                event_type=TimelineEventType.call,
                timestamp=ts,
                summary=f"{direction.value} call with {number} ({duration}s) [UFDR]",
                source_table="call",
                source_id=call.id,
            )
        )
        summary.calls += 1

    def _ingest_message(self, session, case, fields, summary):
        ts = _parse_timestamp(_get(fields, TIMESTAMP_FIELDS))
        if ts is None:
            summary.errors.append("skipped a message record with missing/unparseable timestamp")
            return

        sender = _get(fields, FROM_FIELDS) or "unknown"
        recipient = _get(fields, TO_FIELDS) or "unknown"
        body = _get(fields, BODY_FIELDS) or ""
        app = _get(fields, SOURCE_APP_FIELDS) or "ufdr"

        msg = Message(case_id=case.id, sender=sender, recipient=recipient, body=body, timestamp=ts, app=app)
        session.add(msg)
        session.flush()
        preview = (body[:60] + "...") if len(body) > 60 else body
        session.add(
            TimelineEvent(
                case_id=case.id,
                event_type=TimelineEventType.message,
                timestamp=ts,
                summary=f"{sender} -> {recipient}: {preview}",
                source_table="message",
                source_id=msg.id,
            )
        )
        summary.messages += 1

    def _ingest_media(self, session, case, fields, zf, extract_dir, summary, seen_names):
        path_hint = _get(fields, PATH_FIELDS)
        filename = _get(fields, FILENAME_FIELDS) or (Path(path_hint).name if path_hint else None)
        if not filename:
            summary.errors.append("skipped a media record with no filename/path field")
            return

        member = self._find_member(zf, path_hint, filename)
        if member is None:
            summary.errors.append(f"referenced media file not found in archive: {path_hint or filename}")
            return

        info = zf.getinfo(member)
        if info.file_size > MAX_EXTRACT_BYTES:
            summary.errors.append(f"{filename}: skipped, {info.file_size} bytes exceeds extraction cap")
            return

        suffix = Path(filename).suffix.lower()
        kind = {
            ".jpg": EvidenceKind.photo, ".jpeg": EvidenceKind.photo, ".png": EvidenceKind.photo,
            ".heic": EvidenceKind.photo, ".webp": EvidenceKind.photo,
            ".mp4": EvidenceKind.video, ".mov": EvidenceKind.video, ".avi": EvidenceKind.video,
            ".wav": EvidenceKind.audio, ".mp3": EvidenceKind.audio, ".m4a": EvidenceKind.audio,
            ".ogg": EvidenceKind.audio, ".flac": EvidenceKind.audio,
        }.get(suffix, EvidenceKind.other)

        safe_name = filename
        counter = 1
        while safe_name in seen_names:
            stem, dot, ext = filename.rpartition(".")
            safe_name = f"{stem or filename}_{counter}{dot}{ext if dot else ''}"
            counter += 1
        seen_names.add(safe_name)

        dest = extract_dir / safe_name
        dest.write_bytes(zf.read(member))

        captured_at = lat = lon = None
        if kind == EvidenceKind.photo:
            captured_at, lat, lon = _read_exif(dest)
        if captured_at is None:
            captured_at = _parse_timestamp(_get(fields, TIMESTAMP_FIELDS))

        evidence = EvidenceFile(
            case_id=case.id,
            kind=kind,
            original_path=str(dest),
            file_name=filename,
            sha256=sha256_of_file(dest),
            size_bytes=info.file_size,
            captured_at=captured_at,
            latitude=lat,
            longitude=lon,
        )
        session.add(evidence)
        session.flush()

        event_type = {
            EvidenceKind.photo: TimelineEventType.photo,
            EvidenceKind.video: TimelineEventType.video,
            EvidenceKind.audio: TimelineEventType.audio,
        }.get(kind)
        if event_type is not None:
            session.add(
                TimelineEvent(
                    case_id=case.id,
                    event_type=event_type,
                    timestamp=captured_at or evidence.created_at,
                    summary=f"{kind.value} evidence ingested from UFDR: {filename}",
                    source_table="evidencefile",
                    source_id=evidence.id,
                    latitude=lat,
                    longitude=lon,
                )
            )

        if kind == EvidenceKind.photo:
            summary.photos += 1
        elif kind == EvidenceKind.video:
            summary.videos += 1
        elif kind == EvidenceKind.audio:
            summary.audio_files += 1

        audit_log.append_entry(
            session,
            actor="system",
            action="ingest.file",
            case_id=case.id,
            payload={"file_name": filename, "sha256": evidence.sha256, "kind": kind.value},
        )

    @staticmethod
    def _find_member(zf: zipfile.ZipFile, path_hint: str | None, filename: str) -> str | None:
        names = zf.namelist()
        if path_hint:
            normalized = path_hint.replace("\\", "/").lstrip("/")
            for n in names:
                if n.replace("\\", "/") == normalized:
                    return n
        matches = [n for n in names if n.replace("\\", "/").rsplit("/", 1)[-1] == filename]
        return matches[0] if matches else None
