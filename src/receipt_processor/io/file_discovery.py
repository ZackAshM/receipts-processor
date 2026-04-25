"""Discover supported receipt files in a directory."""

from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".jpeg", ".jpg", ".png"}


def discover_receipt_files(input_dir: Path) -> list[Path]:
    """Return sorted receipt files with supported extensions."""
    files = [
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files)
