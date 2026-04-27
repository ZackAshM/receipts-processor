"""Deterministic structured extraction from OCR text and line artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from receipt_processor.extraction.ocr_router import DocumentExtraction
from receipt_processor.extraction.receipt_parser import parse_receipt_text
from receipt_processor.extraction.transaction_type import normalize_transaction_type

AMOUNT_AT_END_RE = re.compile(r"^(?P<name>.+?)\s+(?P<amount>\$?\d+(?:[.,]\d{2}))\s*$")

FIELD_KEYWORD_PATTERNS: dict[str, tuple[str, ...]] = {
    "subtotal": ("subtotal", "sub total"),
    "tax": (" tax", "sales tax", "vat"),
    "tip": (" tip", "gratuity"),
    "service_charge": ("service charge", "svc charge", "service fee"),
    "pre_tip_total": ("pre-tip total", "pre tip total", "total before tip"),
    "amount_paid": ("amount paid", "amount due", "grand total", "total due", "balance due", "total"),
}

LINE_ITEM_EXCLUDE_KEYWORDS = {
    "subtotal",
    "total",
    "tax",
    "tip",
    "gratuity",
    "service",
    "amount paid",
    "amount due",
    "balance due",
    "change",
    "cash",
    "card",
    "tender",
    "auth amt",
    "charge detail",
    "approval",
}


def _to_float(value: str) -> float | None:
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _detect_document_type(receipt_path: Path, raw_text: str) -> str:
    name = receipt_path.name.lower()
    text = raw_text.lower()
    if any(token in name or token in text for token in ("statement", "account statement", "monthly statement")):
        return "statement"
    if any(token in name or token in text for token in ("email", "from:", "subject:")):
        return "email"
    return "receipt"


def _detect_currency(raw_text: str) -> str:
    lowered = raw_text.lower()
    if " usd" in lowered or "$" in raw_text:
        return "USD"
    if " eur" in lowered or "€" in raw_text:
        return "EUR"
    if " gbp" in lowered or "£" in raw_text:
        return "GBP"
    return ""


def _extract_amount_by_keywords(lines: list[str]) -> tuple[dict[str, float | None], dict[str, str]]:
    values: dict[str, float | None] = {field: None for field in FIELD_KEYWORD_PATTERNS}
    used_keywords: dict[str, str] = {}
    for line in lines:
        lowered = f" {line.lower()} "
        for field, patterns in FIELD_KEYWORD_PATTERNS.items():
            if values[field] is not None:
                continue
            if not any(pattern in lowered for pattern in patterns):
                continue
            matches = re.findall(r"(\$?\d+(?:[.,]\d{2}))", line)
            if not matches:
                continue

            # Amount paid should not accidentally lock onto subtotal lines.
            if field == "amount_paid" and "subtotal" in lowered and not any(
                token in lowered for token in ("amount paid", "amount due", "grand total", "total due", "balance due")
            ):
                continue

            # Use the right-most amount token. This handles lines like:
            # "Tax 8.375% 1.14" where the first numeric value is not the tax amount.
            amount = _to_float(matches[-1])
            if amount is None:
                continue
            values[field] = amount
            used_keywords[field] = line.strip()
    return values, used_keywords


def _line_items_from_text_lines(lines: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in lines:
        match = AMOUNT_AT_END_RE.match(line.strip())
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group("name")).strip(" -:\t")
        if not name:
            continue
        lowered_name = name.lower()
        if any(token in lowered_name for token in LINE_ITEM_EXCLUDE_KEYWORDS):
            continue
        amount = _to_float(match.group("amount"))
        if amount is None:
            continue
        items.append(
            {
                "name": name,
                "amount": round(amount, 2),
                "is_highlighted": False,
                "source": "text",
            }
        )
    return items


def _line_items_from_ocr_lines(document: DocumentExtraction) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in document.ocr_lines:
        match = AMOUNT_AT_END_RE.match(line.text.strip())
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group("name")).strip(" -:\t")
        if not name:
            continue
        lowered_name = name.lower()
        if any(token in lowered_name for token in LINE_ITEM_EXCLUDE_KEYWORDS):
            continue
        amount = _to_float(match.group("amount"))
        if amount is None:
            continue
        items.append(
            {
                "name": name,
                "amount": round(amount, 2),
                "is_highlighted": bool(line.is_highlighted),
                "source": "ocr",
            }
        )
    return items


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    for item in items:
        key = (str(item.get("name", "")).lower(), float(item.get("amount", 0.0)))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _confidence_from_core_fields(merchant_name: str, transaction_date: str, amount_paid: float | None) -> float:
    filled = 0
    total = 3
    if merchant_name:
        filled += 1
    if transaction_date:
        filled += 1
    if amount_paid is not None:
        filled += 1
    return round(filled / total, 4)


def extract_structured_data(receipt_path: Path, document: DocumentExtraction) -> dict[str, Any]:
    """Extract deterministic structured fields from a receipt document."""
    raw_text = document.raw_text or ""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    parsed = parse_receipt_text(raw_text)
    totals, used_keywords = _extract_amount_by_keywords(lines)
    ocr_items = _line_items_from_ocr_lines(document)
    text_items = _line_items_from_text_lines(lines)
    line_items = _dedupe_items(ocr_items + text_items)

    has_highlights = any(bool(item.get("is_highlighted")) for item in line_items)

    amount_paid = totals.get("amount_paid")
    if amount_paid is None:
        parsed_amount = _to_float(parsed.get("amount", "")) if parsed.get("amount") else None
        amount_paid = parsed_amount

    merchant_name = parsed.get("vendor", "")
    transaction_date = parsed.get("date", "")
    parsed_type = str(parsed.get("expense_type", "")).strip()
    transaction_type = normalize_transaction_type(
        parsed_type,
        context_text=f"{merchant_name} {raw_text}",
        default="",
    )

    confidence = _confidence_from_core_fields(merchant_name, transaction_date, amount_paid)
    needs_review = confidence < 0.7 or (not line_items and amount_paid is None)

    return {
        "filename": receipt_path.name,
        "document_type": _detect_document_type(receipt_path, raw_text),
        "merchant_name": merchant_name,
        "transaction_date": transaction_date,
        "transaction_type": transaction_type,
        "currency": _detect_currency(raw_text),
        "line_items": line_items,
        "subtotal": totals.get("subtotal"),
        "tax": totals.get("tax"),
        "tip": totals.get("tip"),
        "service_charge": totals.get("service_charge"),
        "pre_tip_total": totals.get("pre_tip_total"),
        "amount_paid": amount_paid,
        "used_keywords": used_keywords,
        "confidence": confidence,
        "needs_review": needs_review,
        "highlight_detection_available": document.highlight_detection_available,
        "has_highlighted_contributions": has_highlights,
        "raw_text_length": len(raw_text),
    }
