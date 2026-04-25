"""Confidence scoring for extracted records."""

from __future__ import annotations

import re

OPTIONAL_COLUMN_HINTS = (
    "receipt amt",
    "receipt amount",
    "if different",
    "optional",
)


def _is_optional_column(column_name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", column_name.lower()).strip()
    return any(hint in normalized for hint in OPTIONAL_COLUMN_HINTS)


def calculate_confidence(record: dict) -> float:
    """Compute confidence ratio across required-like model fields."""
    if not record:
        return 0.0

    non_empty = 0
    total = 0
    for key, value in record.items():
        if key.startswith("_"):
            continue
        if _is_optional_column(key):
            continue
        total += 1
        if value not in (None, ""):
            non_empty += 1

    if total == 0:
        return 0.0

    return round(non_empty / total, 4)
