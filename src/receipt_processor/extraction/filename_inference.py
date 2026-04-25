"""Infer missing fields from receipt filenames."""

import re

AMOUNT_PATTERN = re.compile(r"(?P<amount>\d+[\.,]\d{2})")
DATE_PATTERN = re.compile(r"(?P<date>\d{4}[-_]\d{2}[-_]\d{2})")


def infer_fields_from_filename(filename: str, current_fields: dict) -> dict:
    """Infer expense fields using filename patterns."""
    inferred: dict[str, str] = {}

    amount_match = AMOUNT_PATTERN.search(filename)
    if amount_match and not current_fields.get("amount"):
        inferred["amount"] = amount_match.group("amount").replace(",", ".")

    date_match = DATE_PATTERN.search(filename)
    if date_match and not current_fields.get("date"):
        inferred["date"] = date_match.group("date").replace("_", "-")

    cleaned = re.sub(r"[_\-]", " ", filename)
    cleaned = re.sub(r"\.[a-zA-Z0-9]+$", "", cleaned)
    if cleaned and not current_fields.get("vendor"):
        inferred["vendor"] = cleaned

    return inferred
