"""Sanitization helpers for spreadsheet-safe exports."""

from __future__ import annotations

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_spreadsheet_cell(value: object) -> object:
    """Neutralize spreadsheet formula injection for string-like values.

    Spreadsheet apps can execute formulas when a cell starts with certain
    characters. Prefix risky text with an apostrophe to force literal content.
    """
    if not isinstance(value, str):
        return value

    if value == "":
        return value

    stripped = value.lstrip()
    if stripped.startswith(DANGEROUS_PREFIXES):
        return f"'{value}"

    return value
