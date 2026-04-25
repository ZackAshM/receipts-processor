"""OCR entrypoint abstraction."""

from pathlib import Path


def extract_text(receipt_path: Path) -> str:
    """Return extracted text for a receipt.

    Placeholder implementation for project bootstrap.
    """
    _ = receipt_path
    return ""
