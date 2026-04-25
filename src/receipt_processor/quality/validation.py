"""Validation checks for expense records."""

from __future__ import annotations

import re


def _normalize(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _find_column(record: dict[str, str], candidates: tuple[str, ...]) -> str:
    for key in record.keys():
        normalized = _normalize(key)
        for candidate in candidates:
            if candidate in normalized:
                return key
    return ""


def validate_expense_record(record: dict[str, str]) -> tuple[bool, list[str]]:
    """Return validation state and error messages."""
    errors: list[str] = []

    date_col = _find_column(record, ("date",))
    description_col = _find_column(record, ("description", "memo", "details", "vendor"))
    amount_col = _find_column(record, ("amt claimed", "amount", "total"))

    if not date_col or not str(record.get(date_col, "")).strip():
        errors.append("Missing required field: date")
    if not description_col or not str(record.get(description_col, "")).strip():
        errors.append("Missing required field: description/vendor")
    if not amount_col or not str(record.get(amount_col, "")).strip():
        errors.append("Missing required field: amount")

    return (len(errors) == 0, errors)
