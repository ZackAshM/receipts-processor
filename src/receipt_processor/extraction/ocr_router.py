"""OCR and text extraction entrypoint abstraction."""

from __future__ import annotations

import os
from pathlib import Path

from receipt_processor.io.format_detector import detect_receipt_format


def _extract_text_from_pdf(receipt_path: Path) -> str:
    """Extract concatenated text from a PDF file."""
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    text_parts: list[str] = []
    try:
        reader = PdfReader(str(receipt_path))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
    except Exception:
        return ""

    return "\n".join(text_parts).strip()


def _extract_text_from_image(receipt_path: Path) -> str:
    """Extract text from an image file using Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""

    tess_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

    try:
        with Image.open(receipt_path) as image:
            return (pytesseract.image_to_string(image) or "").strip()
    except Exception:
        return ""


def extract_text(receipt_path: Path) -> str:
    """Return extracted text for a receipt path."""
    file_kind = detect_receipt_format(receipt_path)
    if file_kind == "pdf":
        return _extract_text_from_pdf(receipt_path)
    if file_kind == "image":
        return _extract_text_from_image(receipt_path)
    return ""
