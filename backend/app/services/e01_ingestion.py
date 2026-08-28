"""E01 (EnCase Evidence Format) ingestion adapter.

Walks the filesystem(s) inside a raw disk/device image using pytsk3, which
has native EWF support built into its TSK_IMG_TYPE_EWF_EWF image type -- no
separate read bridge is needed, pytsk3.Img_Info() opens .E01 files directly
(auto-discovering .E02/.E03/... segments). pyewf (libewf-python) is used
only for an upfront file-signature check, so a bad path fails with a clear
message instead of a raw TSK exception.

Unlike CaseFolderParser, this does not parse per-app databases (Android
contacts2.db, iOS AddressBook.sqlitedb, WhatsApp msgstore.db, etc.) into
Contact/Call/Message rows -- each has its own schema per OS/app version and
is out of scope here. Known artifact databases are still extracted (as
EvidenceKind.document) with a note in IngestSummary.errors so nothing is
silently dropped. .eml files are the one exception: RFC 822 is a single
standard format parseable with the stdlib `email` module, so those get
turned into Message rows the same way UFDR SMS/chat records do.
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.config import get_settings
from app.models.case import Case
from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.models.message import Message
from app.models.registry_artifact import RegistryArtifact
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.services import audit_log, registry_artifacts
from app.services.email_parsing import format_message_body, parse_eml
from app.services.ingestion import (
    AUDIO_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    EMAIL_EXTENSIONS,
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    IngestSummary,
    UFDRParser,
    _read_exif,
    sha256_of_file,
)

logger = logging.getLogger("netsherlock.e01_ingestion")

E01_EXTENSIONS = {".e01", ".s01", ".l01", ".ex01"}

# Raw/dd-style device images and VM disk containers -- pytsk3 opens these
# directly via its own format auto-detection, no separate decode library
# needed the way EWF needs pyewf. (.vmdk/.vhd/.vhdx only work if the
# installed libtsk build was compiled with libvmdk/libvhdi support; if not,
# opening raises and the resulting error is surfaced same as any other
# unreadable image.)
RAW_EXTENSIONS = {".dd", ".img", ".raw", ".001", ".vmdk", ".vhd", ".vhdx"}

KNOWN_ARTIFACT_FILENAMES = {
    "contacts2.db": "Android contacts database",
    "mmssms.db": "Android SMS/MMS database",
    "sms.db": "iOS Messages database",
    "msgstore.db": "WhatsApp message store",
    "addressbook.sqlitedb": "iOS Address Book database",
    "callhistory.storedata": "iOS Call History database",
}

MAX_EXTRACT_BYTES = 200 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
PER_FILE_READ_TIMEOUT_SECONDS = 20

_available: bool | None = None


def is_available() -> bool:
    """True if both pytsk3 and pyewf are installed.

    pytsk3 wheels declare a TSK_IMG_TYPE_EWF_EWF image type, which looks like
    native EWF support, but in practice (confirmed against a real .E01 on
    this build) pytsk3.Img_Info() opens .E01 files as a RAW image instead of
    decoding the EWF container -- it returns the literal EWF file bytes, not
    the disk content. pyewf (libewf-python) is required to actually decode
    the container; _EWFImgInfo below bridges it into a pytsk3.Img_Info.
    """
    global _available
    if _available is None:
        try:
            import pyewf  # noqa: F401
            import pytsk3  # noqa: F401
        except ImportError:
            _available = False
        else:
            _available = True
    return _available


_raw_available: bool | None = None


def raw_is_available() -> bool:
    """True if pytsk3 is installed. Unlike E01, raw/dd images need no
    separate decode library -- pytsk3 reads them directly."""
    global _raw_available
    if _raw_available is None:
        try:
            import pytsk3  # noqa: F401
        except ImportError:
            _raw_available = False
        else:
            _raw_available = True
    return _raw_available


def _open_ewf_image(source: Path):
    """Opens source through pyewf and bridges it into a pytsk3.Img_Info so
    TSK reads decoded disk bytes instead of the raw EWF container."""
    import pytsk3
    import pyewf

    handle = pyewf.handle()
    handle.open(pyewf.glob(str(source)))

    class _EWFImgInfo(pytsk3.Img_Info):
        def __init__(self):
            self._handle = handle
            super().__init__(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)

        def close(self):
            self._handle.close()

        def read(self, offset, size):
            self._handle.seek(offset)
            return self._handle.read(size)

        def get_size(self):
            return self._handle.get_media_size()

    return _EWFImgInfo()


def _open_raw_image(source: Path):
    """Opens a raw/dd image (or a VM disk container, if libtsk was built
    with vmdk/vhdi support) via pytsk3's own format detection -- no
    separate decode bridge needed."""
    import pytsk3

    return pytsk3.Img_Info(str(source))


def _open_volume(img):
    """Try each partition-table type explicitly. pytsk3's combined DETECT
    mode chains through DOS/GPT/etc and a failure in one (e.g. a GPT backup
    header read near the end of the disk) aborts detection entirely instead
    of falling through to the next type, so we drive the fallback ourselves."""
    import pytsk3

    for vstype in (
        pytsk3.TSK_VS_TYPE_DOS,
        pytsk3.TSK_VS_TYPE_GPT,
        pytsk3.TSK_VS_TYPE_MAC,
        pytsk3.TSK_VS_TYPE_BSD,
        pytsk3.TSK_VS_TYPE_SUN,
    ):
        try:
            return pytsk3.Volume_Info(img, vstype)
        except Exception:
            continue
    return None


def _open_filesystem(img, offset: int):
    """Try DETECT first, then each concrete filesystem type explicitly (same
    reasoning as _open_volume: DETECT's own entropy/encryption heuristic has
    produced false positives here when fed certain data). Collects every
    attempt's error instead of keeping only the last one, since a genuine
    I/O failure (e.g. an unreadable region of the image) will fail every
    type identically and the *first* attempt (DETECT, or the fstype that
    actually matches the partition) is the meaningful one to report."""
    import pytsk3

    attempts: list[tuple[str, Exception]] = []
    try:
        return pytsk3.FS_Info(img, offset=offset)
    except Exception as exc:
        attempts.append(("DETECT", exc))

    for name, fstype in (
        ("NTFS", pytsk3.TSK_FS_TYPE_NTFS_DETECT),
        ("FAT", pytsk3.TSK_FS_TYPE_FAT_DETECT),
        ("EXT", pytsk3.TSK_FS_TYPE_EXT_DETECT),
        ("HFS+", pytsk3.TSK_FS_TYPE_HFS_DETECT),
        ("ISO9660", pytsk3.TSK_FS_TYPE_ISO9660_DETECT),
    ):
        try:
            return pytsk3.FS_Info(img, offset, fstype)
        except Exception as exc:
            attempts.append((name, exc))

    unique_messages = {str(exc) for _, exc in attempts}
    if len(unique_messages) == 1:
        raise RuntimeError(f"every filesystem-type probe failed identically: {unique_messages.pop()}")
    raise RuntimeError("; ".join(f"{name}: {exc}" for name, exc in attempts))


@dataclass
class _Entry:
    tsk_file: "object"
    path: str
    is_deleted: bool


def _classify(name: str) -> EvidenceKind | None:
    """Every real file on the image is evidence, the same way Autopsy's own
    file browser lists everything -- unlike CaseFolderParser/UFDR ingestion
    (which only know about a fixed photos/audio export shape), an E01 image
    is a full filesystem and most of what's on it won't be a photo or video.
    NTFS/filesystem-internal metadata (`$MFT`, `$LogFile`, ...) is skipped:
    it isn't user content and would just flood the evidence list with noise."""
    if name.startswith("$"):
        return None

    suffix = Path(name).suffix.lower()
    if suffix in PHOTO_EXTENSIONS:
        return EvidenceKind.photo
    if suffix in VIDEO_EXTENSIONS:
        return EvidenceKind.video
    if suffix in AUDIO_EXTENSIONS:
        return EvidenceKind.audio
    if suffix in DOCUMENT_EXTENSIONS or suffix in EMAIL_EXTENSIONS or name.lower() in KNOWN_ARTIFACT_FILENAMES:
        return EvidenceKind.document
    return EvidenceKind.other


def _derive_owner(image_path: str) -> str | None:
    """For a per-user hive (NTUSER.DAT), the username is the parent
    directory of its in-image path, e.g. `/Documents and Settings/jean/NTUSER.DAT`
    or `/Users/jean/NTUSER.DAT` -> "jean". Machine-wide hives (SOFTWARE/SYSTEM)
    have no single owner, so callers only use this for NTUSER.DAT."""
    parts = [p for p in image_path.split("/") if p]
    return parts[-2] if len(parts) >= 2 else None


def _walk_filesystem(fs, summary: IngestSummary):
    """Yield _Entry for every regular file in the filesystem, recursively."""
    import pytsk3

    def _recurse(directory, path: str, visited_inodes: set[int], depth: int):
        if depth > 256:
            summary.errors.append(f"{path}: directory nesting too deep, stopped recursing")
            return
        try:
            entries = list(directory)
        except Exception as exc:
            summary.errors.append(f"{path}: failed to list directory ({exc})")
            return

        for entry in entries:
            try:
                info_name = entry.info.name
                meta = entry.info.meta
            except AttributeError:
                continue
            if info_name is None or meta is None:
                continue

            raw_name = info_name.name
            name = raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else raw_name
            if name in (".", ".."):
                continue

            full_path = f"{path}/{name}"
            is_deleted = bool(meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)

            if meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                if meta.addr in visited_inodes:
                    continue
                visited_inodes.add(meta.addr)
                try:
                    sub_dir = entry.as_directory()
                except Exception:
                    continue
                yield from _recurse(sub_dir, full_path, visited_inodes, depth + 1)
            elif meta.type == pytsk3.TSK_FS_META_TYPE_REG:
                yield _Entry(tsk_file=entry, path=full_path, is_deleted=is_deleted)

    root = fs.open_dir(path="/")
    yield from _recurse(root, "", set(), 0)


def _read_content(tsk_file, size: int, path: str, summary: IngestSummary) -> bytes | None:
    """Reads a file's full content off the image via TSK.

    Run on a background thread with a hard wall-clock budget: on a real
    multi-gigabyte disk image, a single damaged/heavily-fragmented file's
    read_random() calls can block far longer than any individual chunk
    timeout would catch, and pytsk3/pyewf give no way to cancel a call
    that's already in flight. Without this, one bad file among tens of
    thousands hangs the entire ingest indefinitely. The abandoned thread is
    a daemon, so it can't block process shutdown; it's a deliberate leak,
    not a real fix for whatever made that one read hang.
    """
    if size <= 0:
        return b""
    if size > MAX_EXTRACT_BYTES:
        summary.errors.append(f"{path}: skipped, {size} bytes exceeds the {MAX_EXTRACT_BYTES} byte extraction cap")
        return None

    result: dict = {}

    def _do_read():
        try:
            chunks = []
            offset = 0
            while offset < size:
                data = tsk_file.read_random(offset, min(CHUNK_SIZE, size - offset))
                if not data:
                    break
                chunks.append(data)
                offset += len(data)
            result["data"] = b"".join(chunks)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=_do_read, daemon=True)
    thread.start()
    thread.join(timeout=PER_FILE_READ_TIMEOUT_SECONDS)

    if thread.is_alive():
        summary.errors.append(
            f"{path}: read timed out after {PER_FILE_READ_TIMEOUT_SECONDS}s and was skipped "
            "(likely fragmented/damaged on this image)"
        )
        return None
    if "error" in result:
        summary.errors.append(f"{path}: read failed ({result['error']})")
        return None
    return result.get("data", b"")


class _TskImageParser(UFDRParser):
    """Shared pytsk3 filesystem-walk pipeline for image-backed parsers.

    E01Parser and RawImageParser differ only in how the pytsk3 image handle
    gets opened (EWF-decoded vs. raw bytes) -- everything downstream
    (partition/filesystem probing, recursive file walk, extraction) is
    identical, so it lives here once.
    """

    _backend_label = "image"

    def _open_image(self, source: Path, summary: IngestSummary):
        raise NotImplementedError

    def ingest(self, session: Session, case: Case, source: Path, data_source_id: int | None = None) -> IngestSummary:
        import pytsk3

        summary = IngestSummary()

        try:
            img = self._open_image(source, summary)
        except Exception as exc:
            summary.errors.append(f"failed to open image via {self._backend_label}: {exc}")
            return summary

        filesystems = []
        volume = _open_volume(img)

        if volume is not None:
            for part in volume:
                if not (part.flags & pytsk3.TSK_VS_PART_FLAG_ALLOC):
                    continue
                try:
                    fs = _open_filesystem(img, offset=part.start * volume.info.block_size)
                except Exception as exc:
                    desc = part.desc.decode("utf-8", errors="replace") if isinstance(part.desc, bytes) else part.desc
                    summary.errors.append(f"partition {part.addr} ({desc}) could not be opened as a filesystem: {exc}")
                    continue
                filesystems.append(fs)
        else:
            try:
                filesystems.append(_open_filesystem(img, offset=0))
            except Exception as exc:
                summary.errors.append(f"no partition table found, and no filesystem found at offset 0: {exc}")

        if not filesystems:
            summary.errors.append(
                "no readable filesystem found in image -- if this is a multi-segment E01 "
                "(.E01/.E02/.E03/...), make sure every segment file is present alongside the first one; "
                "if this is a raw/dd image, confirm it wasn't truncated during acquisition/upload"
            )
            return summary

        extract_dir = get_settings().storage_path / "extracted" / f"case_{case.id}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        seen_names: set[str] = set()
        for fs in filesystems:
            for entry in _walk_filesystem(fs, summary):
                self._ingest_file(session, case, entry, extract_dir, summary, seen_names, data_source_id)

        logger.info(
            "%s ingest for case %s: filesystems_found=%d",
            type(self).__name__, case.id, len(filesystems),
        )

        audit_log.append_entry(
            session,
            actor="system",
            action="ingest.case",
            case_id=case.id,
            payload={"source": str(source), "summary": summary.__dict__},
        )
        return summary

    def _ingest_file(self, session, case, entry: _Entry, extract_dir: Path, summary: IngestSummary, seen_names: set[str], data_source_id: int | None = None):
        name = entry.path.rsplit("/", 1)[-1]
        kind = _classify(name)
        if kind is None:
            return

        try:
            size = entry.tsk_file.info.meta.size
        except AttributeError:
            return

        content = _read_content(entry.tsk_file, size, entry.path, summary)
        if content is None:
            return

        safe_name = name
        counter = 1
        while safe_name in seen_names:
            stem, dot, ext = name.rpartition(".")
            safe_name = f"{stem or name}_{counter}{dot}{ext if dot else ''}"
            counter += 1
        seen_names.add(safe_name)

        dest = extract_dir / safe_name
        dest.write_bytes(content)

        captured_at = lat = lon = None
        if kind == EvidenceKind.photo:
            captured_at, lat, lon = _read_exif(dest)

        recovered = entry.is_deleted and len(content) > 0

        evidence = EvidenceFile(
            case_id=case.id,
            data_source_id=data_source_id,
            kind=kind,
            original_path=str(dest),
            file_name=name,
            sha256=sha256_of_file(dest),
            size_bytes=len(content),
            captured_at=captured_at,
            latitude=lat,
            longitude=lon,
            deleted_then_recovered=recovered,
        )
        session.add(evidence)
        session.flush()

        if name.lower() in KNOWN_ARTIFACT_FILENAMES:
            summary.errors.append(
                f"{entry.path}: {KNOWN_ARTIFACT_FILENAMES[name.lower()]} found — contains contacts/messages, "
                f"automatic parsing not implemented, extracted to {dest} for manual review"
            )

        hive_name = registry_artifacts.identify_hive(name)
        if hive_name is not None:
            self._ingest_registry_hive(session, case, entry, dest, hive_name, evidence, summary, data_source_id)

        if Path(name).suffix.lower() in EMAIL_EXTENSIONS:
            self._ingest_email(session, case, entry.path, content, evidence, summary)

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
                    timestamp=captured_at or datetime.utcnow(),
                    summary=f"{kind.value} evidence ingested from image: {name}"
                    + (" (deleted, recovered)" if recovered else ""),
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
            payload={"file_name": name, "sha256": evidence.sha256, "kind": kind.value, "recovered": recovered},
        )
        session.commit()

    def _ingest_email(self, session, case, path: str, content: bytes, evidence: EvidenceFile, summary: IngestSummary):
        """Parses a .eml found on the image into a Message row, same as
        UFDR SMS/chat records -- keeps the raw file as its own EvidenceFile
        (already created by the caller) regardless of whether parsing
        succeeds, since a malformed .eml is still real evidence."""
        parsed = parse_eml(content)
        if parsed is None or parsed.sent_at is None:
            summary.errors.append(
                f"{path}: could not parse email headers (missing/unparseable From or Date); kept as a document only"
            )
            return

        recipient = ", ".join(parsed.recipients) if parsed.recipients else "unknown"
        msg = Message(
            case_id=case.id,
            sender=parsed.sender,
            recipient=recipient,
            body=format_message_body(parsed),
            timestamp=parsed.sent_at,
            app="email",
        )
        session.add(msg)
        session.flush()
        preview = (msg.body[:60] + "...") if len(msg.body) > 60 else msg.body
        session.add(
            TimelineEvent(
                case_id=case.id,
                event_type=TimelineEventType.message,
                timestamp=parsed.sent_at,
                summary=f"{msg.sender} -> {recipient}: {preview} [from image]",
                source_table="message",
                source_id=msg.id,
            )
        )
        summary.messages += 1

    def _ingest_registry_hive(
        self,
        session,
        case,
        entry: _Entry,
        dest: Path,
        hive_name: str,
        evidence: EvidenceFile,
        summary: IngestSummary,
        data_source_id: int | None,
    ):
        """Parses a registry hive (SOFTWARE/SYSTEM/NTUSER.DAT) already
        extracted to `dest` into RegistryArtifact rows, the same way
        _ingest_email turns a .eml into a Message -- the hive itself stays
        its own EvidenceFile (already created by the caller) regardless of
        whether parsing succeeds."""
        if not registry_artifacts.is_available():
            summary.errors.append(
                f"{entry.path}: registry hive found — regipy not installed, extracted to {dest} but not parsed"
            )
            return

        owner = _derive_owner(entry.path) if hive_name == "NTUSER.DAT" else None

        try:
            parsed = registry_artifacts.parse_hive(dest, hive_name)
        except Exception as exc:
            summary.errors.append(f"{entry.path}: registry hive parsing failed ({exc})")
            return

        for artifact in parsed:
            session.add(
                RegistryArtifact(
                    case_id=case.id,
                    data_source_id=data_source_id,
                    evidence_file_id=evidence.id,
                    kind=artifact.kind,
                    hive=hive_name,
                    owner=owner,
                    key_path=artifact.key_path,
                    name=artifact.name,
                    value=artifact.value,
                    raw_json=json.dumps(artifact.raw, default=str),
                    timestamp=artifact.timestamp,
                )
            )
            summary.registry_artifacts += 1


class E01Parser(_TskImageParser):
    _backend_label = "libewf"

    def _open_image(self, source: Path, summary: IngestSummary):
        import pyewf

        if not pyewf.check_file_signature(str(source)):
            summary.errors.append(f"{source} does not look like an EWF/E01 file; attempting to open anyway")
        return _open_ewf_image(source)


class RawImageParser(_TskImageParser):
    """Handles raw/dd-style device images and VM disk containers
    (.dd/.img/.raw/.001/.vmdk/.vhd/.vhdx) -- opened directly via pytsk3
    with no separate decode library."""

    _backend_label = "pytsk3 (raw image)"

    def _open_image(self, source: Path, summary: IngestSummary):
        return _open_raw_image(source)


def resolve_parser(source: Path) -> UFDRParser:
    """Pick the right ingestion backend for a case-export folder, .E01/raw
    disk image, or .UFDR archive."""
    from app.services.ingestion import CaseFolderParser
    from app.services.ufdr_ingestion import UFDR_EXTENSIONS, CellebriteUFDRParser

    if source.is_dir():
        return CaseFolderParser()

    if source.is_file() and source.suffix.lower() in E01_EXTENSIONS:
        if not is_available():
            raise ValueError(
                f"'{source}' looks like an E01 image, but E01 support isn't installed "
                "(pip install pytsk3 libewf-python)"
            )
        return E01Parser()

    if source.is_file() and source.suffix.lower() in RAW_EXTENSIONS:
        if not raw_is_available():
            raise ValueError(
                f"'{source}' looks like a raw/dd disk image, but image support isn't installed "
                "(pip install pytsk3)"
            )
        return RawImageParser()

    if source.is_file() and source.suffix.lower() in UFDR_EXTENSIONS:
        return CellebriteUFDRParser()

    all_extensions = sorted(E01_EXTENSIONS | RAW_EXTENSIONS | UFDR_EXTENSIONS)
    raise ValueError(
        f"source_path '{source}' is neither a readable case-export folder nor a "
        f"recognized forensic export file ({', '.join(all_extensions)})"
    )
