"""Redaction for court-disclosure exports: blur faces in images, mask names/numbers in text."""

import re
import uuid
from pathlib import Path

from app.config import get_settings

PHONE_NUMBER_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")


class ModelUnavailableError(RuntimeError):
    pass


def is_available() -> bool:
    try:
        import cv2  # noqa: F401

        return True
    except ImportError:
        return False


def blur_faces(image_path: str, boxes: list[tuple[float, float, float, float]]) -> Path:
    """boxes are (x, y, w, h). Returns the path to a new, blurred copy of the image."""
    try:
        import cv2
    except ImportError as exc:
        raise ModelUnavailableError(
            "Face blurring requires 'opencv-python' — install backend/requirements.txt to enable this feature."
        ) from exc

    settings = get_settings()
    output_dir = settings.storage_path / "redacted"
    output_dir.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")

    height, width = image.shape[:2]
    for x, y, w, h in boxes:
        x1, y1 = max(int(x), 0), max(int(y), 0)
        x2, y2 = min(int(x + w), width), min(int(y + h), height)
        if x2 <= x1 or y2 <= y1:
            continue
        region = image[y1:y2, x1:x2]
        image[y1:y2, x1:x2] = cv2.GaussianBlur(region, (0, 0), sigmaX=15)

    output_path = output_dir / f"{uuid.uuid4().hex}_{Path(image_path).name}"
    cv2.imwrite(str(output_path), image)
    return output_path


def redact_text(text: str, names: list[str]) -> str:
    """Masks known contact names (case-insensitive whole-word) and phone-number-shaped substrings."""
    redacted = text
    for name in sorted(set(n for n in names if n.strip()), key=len, reverse=True):
        redacted = re.sub(rf"\b{re.escape(name)}\b", "[REDACTED NAME]", redacted, flags=re.IGNORECASE)
    redacted = PHONE_NUMBER_RE.sub("[REDACTED NUMBER]", redacted)
    return redacted
