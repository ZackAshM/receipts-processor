"""File format detection helpers."""

from pathlib import Path


def detect_receipt_format(path: Path) -> str:
    """Return a normalized format label for a file path."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".jpeg", ".jpg", ".png"}:
        return "image"
    return "unknown"
