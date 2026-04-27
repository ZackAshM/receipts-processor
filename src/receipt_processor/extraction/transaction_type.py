"""Canonical transaction-type normalization helpers."""

from __future__ import annotations

import re

TRANSACTION_TYPE_CHOICES = ("Food", "Transportation", "Lodging", "Misc")

_TRANSPORT_HINTS = {
    "uber",
    "lyft",
    "taxi",
    "train",
    "metro",
    "subway",
    "bus",
    "flight",
    "airline",
    "airport",
    "parking",
    "toll",
    "rental",
    "car rental",
    "gas",
    "fuel",
}
_FOOD_HINTS = {
    "restaurant",
    "cafe",
    "coffee",
    "bar",
    "bakery",
    "pizza",
    "burger",
    "taqueria",
    "food",
    "dining",
    "meal",
}
_LODGING_HINTS = {
    "hotel",
    "inn",
    "motel",
    "lodge",
    "lodging",
    "airbnb",
    "resort",
    "hostel",
}

_CANONICAL_MAP = {
    "food": "Food",
    "meal": "Food",
    "dining": "Food",
    "transportation": "Transportation",
    "travel": "Transportation",
    "transit": "Transportation",
    "lodging": "Lodging",
    "hotel": "Lodging",
    "accommodation": "Lodging",
    "misc": "Misc",
    "miscellaneous": "Misc",
    "other": "Misc",
    "office supplies": "Misc",
}


def normalize_transaction_type(
    value: str | None,
    *,
    context_text: str = "",
    default: str = "Misc",
) -> str:
    """Return canonical transaction type using fixed choice set."""
    text = (value or "").strip()
    normalized = re.sub(r"\s+", " ", text.lower())
    if normalized in _CANONICAL_MAP:
        return _CANONICAL_MAP[normalized]

    haystack = f"{normalized} {context_text.lower()}".strip()
    if any(hint in haystack for hint in _TRANSPORT_HINTS):
        return "Transportation"
    if any(hint in haystack for hint in _LODGING_HINTS):
        return "Lodging"
    if any(hint in haystack for hint in _FOOD_HINTS):
        return "Food"
    return default
