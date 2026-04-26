"""OCR and text extraction entrypoint abstraction."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

from receipt_processor.io.format_detector import detect_receipt_format

PDF_MIN_TEXT_CHARS_FOR_SKIP_OCR = 60


@dataclass(frozen=True)
class OCRLine:
    """Represents one OCR-derived text line and highlight metadata."""

    text: str
    is_highlighted: bool = False


@dataclass(frozen=True)
class DocumentExtraction:
    """Raw extraction payload used by downstream deterministic parsing."""

    raw_text: str
    ocr_lines: list[OCRLine]
    highlight_detection_available: bool = False


def _extract_text_from_pdf(receipt_path: Path) -> str:
    """Extract concatenated text from a PDF file."""
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    text_parts: list[str] = []
    min_chars = PDF_MIN_TEXT_CHARS_FOR_SKIP_OCR
    try:
        min_chars = int(
            os.environ.get(
                "RECEIPT_PROCESSOR_PDF_MIN_TEXT_CHARS",
                str(PDF_MIN_TEXT_CHARS_FOR_SKIP_OCR),
            )
        )
    except (TypeError, ValueError):
        min_chars = PDF_MIN_TEXT_CHARS_FOR_SKIP_OCR
    min_chars = max(0, min_chars)

    try:
        reader = PdfReader(str(receipt_path))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            normalized_page_text = " ".join(page_text.split())
            if normalized_page_text:
                text_parts.append(page_text)

            needs_page_ocr = len(normalized_page_text) < min_chars

            # Fallback for image-only or low-text PDFs (common for scans/screenshots).
            if not needs_page_ocr:
                continue
            try:
                images = list(page.images)
            except Exception:
                images = []
            for image in images:
                image_text = _extract_text_from_image_bytes(image.data)
                if image_text:
                    text_parts.append(image_text)
    except Exception:
        return ""

    return "\n".join(text_parts).strip()


def _extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Extract text from raw image bytes using Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""

    tess_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return (pytesseract.image_to_string(image) or "").strip()
    except Exception:
        return ""


def _is_highlighted_crop(crop) -> bool:
    """Best-effort highlight detection for marker-like background colors."""
    try:
        hsv = crop.convert("HSV")
        pixels = list(hsv.getdata())
    except Exception:
        return False

    if not pixels:
        return False

    colorful = 0
    marker_like = 0
    for hue, sat, val in pixels:
        if sat >= 55 and val >= 95:
            colorful += 1
            if (
                (18 <= hue <= 45)   # yellow/orange highlighter
                or (46 <= hue <= 95)  # lime/green highlighter
                or (130 <= hue <= 170)  # pink/magenta marker
            ):
                marker_like += 1

    if colorful == 0:
        return False

    ratio = marker_like / colorful
    return ratio >= 0.22


def _extract_ocr_lines_from_image(receipt_path: Path) -> tuple[list[OCRLine], bool]:
    """Extract OCR lines and line-level highlight flags from an image."""
    try:
        import pytesseract
        from pytesseract import Output
        from PIL import Image
    except Exception:
        return [], False

    tess_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

    try:
        with Image.open(receipt_path) as image:
            rgb = image.convert("RGB")
            data = pytesseract.image_to_data(rgb, output_type=Output.DICT)
    except Exception:
        return [], False

    required_keys = {"text", "conf", "left", "top", "width", "height", "block_num", "par_num", "line_num"}
    if not required_keys.issubset(data.keys()):
        return [], False

    grouped: dict[tuple[int, int, int], dict[str, object]] = {}
    count = len(data["text"])
    for idx in range(count):
        text = (data["text"][idx] or "").strip()
        if not text:
            continue

        try:
            conf = float(data["conf"][idx])
        except (TypeError, ValueError):
            conf = 0.0
        if conf <= 0:
            continue

        left = int(data["left"][idx])
        top = int(data["top"][idx])
        width = int(data["width"][idx])
        height = int(data["height"][idx])
        if width <= 0 or height <= 0:
            continue

        key = (
            int(data["block_num"][idx]),
            int(data["par_num"][idx]),
            int(data["line_num"][idx]),
        )
        bucket = grouped.setdefault(key, {"words": [], "highlighted": False})
        words = bucket["words"]
        if isinstance(words, list):
            words.append(text)

        x0 = max(0, left - 2)
        y0 = max(0, top - 2)
        x1 = min(rgb.width, left + width + 2)
        y1 = min(rgb.height, top + height + 2)
        if x1 <= x0 or y1 <= y0:
            continue
        crop = rgb.crop((x0, y0, x1, y1))
        if _is_highlighted_crop(crop):
            bucket["highlighted"] = True

    lines: list[OCRLine] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        words = bucket.get("words", [])
        if not isinstance(words, list):
            continue
        text = " ".join(str(word).strip() for word in words if str(word).strip()).strip()
        if not text:
            continue
        lines.append(OCRLine(text=text, is_highlighted=bool(bucket.get("highlighted"))))
    return lines, True


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
    document = extract_document(receipt_path)
    return document.raw_text


def extract_document(receipt_path: Path) -> DocumentExtraction:
    """Return raw text and optional OCR line metadata for a receipt path."""
    file_kind = detect_receipt_format(receipt_path)
    if file_kind == "pdf":
        return DocumentExtraction(
            raw_text=_extract_text_from_pdf(receipt_path),
            ocr_lines=[],
            highlight_detection_available=False,
        )
    if file_kind == "image":
        lines, highlight_available = _extract_ocr_lines_from_image(receipt_path)
        raw_text = _extract_text_from_image(receipt_path)
        return DocumentExtraction(
            raw_text=raw_text,
            ocr_lines=lines,
            highlight_detection_available=highlight_available,
        )
    return DocumentExtraction(raw_text="", ocr_lines=[], highlight_detection_available=False)
