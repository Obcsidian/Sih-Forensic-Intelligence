"""File signature detection for forensic evidence."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileSignature:
    extension: str
    detected_type: str
    is_match: bool


SIGNATURES = {
    b"\xFF\xD8\xFF": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"%PDF": "pdf",
    b"PK\x03\x04": "zip",
    b"7z\xBC\xAF\x27\x1C": "7z",
    b"Rar!\x1A\x07\x00": "rar",
    b"MZ": "exe",
    b"\x7FELF": "elf",
    b"RIFF": "riff",
}


EXTENSION_TYPES = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".gif": "gif",
    ".pdf": "pdf",
    ".zip": "zip",
    ".7z": "7z",
    ".rar": "rar",
    ".exe": "exe",
    ".dll": "exe",
    ".wav": "riff",
    ".avi": "riff",
}


def detect_file_signature(path: Path) -> FileSignature | None:
    """Detect the actual file type from its magic bytes."""

    if not path.is_file():
        return None

    try:
        with path.open("rb") as file:
            header = file.read(16)
    except OSError:
        return None

    extension = path.suffix.lower()
    expected_type = EXTENSION_TYPES.get(extension)

    detected_type = None

    for signature, file_type in SIGNATURES.items():
        if header.startswith(signature):
            detected_type = file_type
            break

    if detected_type is None:
        return FileSignature(
            extension=extension,
            detected_type="unknown",
            is_match=True,
        )

    return FileSignature(
        extension=extension,
        detected_type=detected_type,
        is_match=(
            expected_type is None
            or expected_type == detected_type
        ),
    )
