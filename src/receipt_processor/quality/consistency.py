"""Consistency and anomaly checks across extraction sources."""

from __future__ import annotations

import re
from datetime import datetime

CORE_FIELDS = ("date", "vendor", "amount")
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y_%m_%d", "%m/%d/%Y", "%m-%d-%Y")


def _normalize_vendor(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _normalize_date(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _normalize_amount(value: str) -> float | None:
    raw = value.strip()
    if not raw:
        return None
    cleaned = raw.replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _vendors_conflict(left: str, right: str) -> bool:
    left_norm = _normalize_vendor(left)
    right_norm = _normalize_vendor(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return False
    if left_norm in right_norm or right_norm in left_norm:
        return False
    return True


def detect_contradictions(source_fields: dict[str, dict[str, str]]) -> list[str]:
    """Detect contradictory values across text/filename/notes sources."""
    contradictions: list[str] = []
    available_sources = [name for name, fields in source_fields.items() if fields]

    for field in CORE_FIELDS:
        for idx, left_name in enumerate(available_sources):
            for right_name in available_sources[idx + 1 :]:
                left_value = source_fields[left_name].get(field, "").strip()
                right_value = source_fields[right_name].get(field, "").strip()
                if not left_value or not right_value:
                    continue

                if field == "amount":
                    left_amount = _normalize_amount(left_value)
                    right_amount = _normalize_amount(right_value)
                    if left_amount is None or right_amount is None:
                        continue
                    if abs(left_amount - right_amount) > 0.009:
                        contradictions.append(
                            f"{field} mismatch ({left_name}={left_value} vs {right_name}={right_value})"
                        )
                elif field == "date":
                    left_date = _normalize_date(left_value)
                    right_date = _normalize_date(right_value)
                    if left_date != right_date:
                        contradictions.append(
                            f"{field} mismatch ({left_name}={left_value} vs {right_name}={right_value})"
                        )
                elif field == "vendor":
                    if _vendors_conflict(left_value, right_value):
                        contradictions.append(
                            f"{field} mismatch ({left_name}={left_value} vs {right_name}={right_value})"
                        )

    return contradictions


def is_null_result(fields: dict[str, str]) -> bool:
    """Return True when no relevant extraction information was found."""
    return not any(fields.get(key, "").strip() for key in CORE_FIELDS)
