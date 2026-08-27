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
silently dropped.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.config import get_settings
from app.models.case import Case
from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.services import audit_log
from app.services.ingestion import (
    AUDIO_EXTENSIONS,
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    IngestSummary,
    UFDRParser,
    _read_exif,
    sha256_of_file,
)

logger = logging.getLogger("forensai.e01_ingestion")

E01_EXTENSIONS = {".e01", ".s01", ".l01", ".ex01"}

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
    suffix = Path(name).suffix.lower()
    if suffix in PHOTO_EXTENSIONS:
        return EvidenceKind.photo
    if suffix in VIDEO_EXTENSIONS:
        return EvidenceKind.video
    if suffix in AUDIO_EXTENSIONS:
        return EvidenceKind.audio
    if name.lower() in KNOWN_ARTIFACT_FILENAMES:
        return EvidenceKind.document
    return None


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
    if size <= 0:
        return b""
    if size > MAX_EXTRACT_BYTES:
        summary.errors.append(f"{path}: skipped, {size} bytes exceeds the {MAX_EXTRACT_BYTES} byte extraction cap")
        return None
    chunks = []
    offset = 0
    try:
        while offset < size:
            data = tsk_file.read_random(offset, min(CHUNK_SIZE, size - offset))
            if not data:
                break
            chunks.append(data)
            offset += len(data)
    except Exception as exc:
        summary.errors.append(f"{path}: read failed ({exc})")
        return None
    return b"".join(chunks)


class E01Parser(UFDRParser):
    def ingest(self, session: Session, case: Case, source: Path) -> IngestSummary:
        import pytsk3

        summary = IngestSummary()

        import pyewf

        if not pyewf.check_file_signature(str(source)):
            summary.errors.append(f"{source} does not look like an EWF/E01 file; attempting to open anyway")

        try:
            img = _open_ewf_image(source)
        except Exception as exc:
            summary.errors.append(f"failed to open image via libewf: {exc}")
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
                "(.E01/.E02/.E03/...), make sure every segment file is present alongside the first one"
            )
            return summary

        extract_dir = get_settings().storage_path / "extracted" / f"case_{case.id}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        seen_names: set[str] = set()
        for fs in filesystems:
            for entry in _walk_filesystem(fs, summary):
                self._ingest_file(session, case, entry, extract_dir, summary, seen_names)

        case_status_note = f"filesystems_found={len(filesystems)}"
        logger.info("E01 ingest for case %s: %s", case.id, case_status_note)

        audit_log.append_entry(
            session,
            actor="system",
            action="ingest.case",
            case_id=case.id,
            payload={"source": str(source), "summary": summary.__dict__},
        )
        return summary

    def _ingest_file(self, session, case, entry: _Entry, extract_dir: Path, summary: IngestSummary, seen_names: set[str]):
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


def resolve_parser(source: Path) -> UFDRParser:
    """Pick the right ingestion backend for a case-export folder, .E01 image, or .UFDR archive."""
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

    if source.is_file() and source.suffix.lower() in UFDR_EXTENSIONS:
        return CellebriteUFDRParser()

    all_extensions = sorted(E01_EXTENSIONS | UFDR_EXTENSIONS)
    raise ValueError(
        f"source_path '{source}' is neither a readable case-export folder nor a "
        f"recognized forensic export file ({', '.join(all_extensions)})"
    )
