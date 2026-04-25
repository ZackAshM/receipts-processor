"""Infer missing fields from receipt filenames."""

from __future__ import annotations

import re

AMOUNT_PATTERN = re.compile(r"(?P<amount>\d+[\.,]\d{2})")
DATE_PATTERN = re.compile(r"(?P<date>\d{4}[-_]\d{2}[-_]\d{2})")
NOISE_TOKENS = {
    "receipt",
    "img",
    "image",
    "scan",
    "screenshot",
    "photo",
    "invoice",
}


def _clean_vendor_from_filename(filename: str) -> str:
    base_name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)

    # Strip known date and amount patterns before inferring vendor text.
    base_name = DATE_PATTERN.sub(" ", base_name)
    base_name = AMOUNT_PATTERN.sub(" ", base_name)

    tokens = re.split(r"[\s_\-]+", base_name)
    filtered = []
    for token in tokens:
        stripped = token.strip()
        if not stripped:
            continue
        if stripped.lower() in NOISE_TOKENS:
            continue
        if stripped.isdigit():
            continue
        filtered.append(stripped)

    if not filtered:
        return ""

    text = " ".join(filtered)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    return text


def infer_fields_from_filename(filename: str, current_fields: dict) -> dict[str, str]:
    """Infer expense fields using filename patterns."""
    inferred: dict[str, str] = {}

    amount_match = AMOUNT_PATTERN.search(filename)
    if amount_match and not current_fields.get("amount"):
        inferred["amount"] = amount_match.group("amount").replace(",", ".")

    date_match = DATE_PATTERN.search(filename)
    if date_match and not current_fields.get("date"):
        inferred["date"] = date_match.group("date").replace("_", "-")

    vendor = _clean_vendor_from_filename(filename)
    if vendor and not current_fields.get("vendor"):
        inferred["vendor"] = vendor
    if vendor and not current_fields.get("description"):
        inferred["description"] = f"Other - {vendor}"

    return inferred
