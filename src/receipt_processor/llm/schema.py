"""Schema validation and normalization for LLM extraction payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from receipt_processor.extraction.transaction_type import normalize_transaction_type
from receipt_processor.llm.client_base import LLMStructuredOutputError

NUMERIC_FIELDS = (
    "subtotal",
    "tax",
    "tip",
    "service_charge",
    "pre_tip_total",
    "amount_paid",
)
SEMANTIC_PRESENCE_FIELDS = {
    "merchant_name",
    "transaction_date",
    "transaction_type",
    "currency",
    "amount_paid",
    "subtotal",
    "tax",
    "tip",
    "service_charge",
    "pre_tip_total",
    "line_items",
    "contributing_items",
    "noncontributing_items",
}


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "")
        if not cleaned:
            return None
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return None
    return None


def _to_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _normalize_items(raw_items: object, field_name: str) -> list[dict[str, Any]]:
    if raw_items is None:
        return []
    if not isinstance(raw_items, list):
        raise LLMStructuredOutputError(f"{field_name} must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        amount = _to_float(item.get("amount"))
        if not name or amount is None:
            continue
        highlighted = _to_bool(item.get("is_highlighted"))
        normalized.append(
            {
                "name": name,
                "amount": amount,
                "is_highlighted": bool(highlighted),
                "source": "llm",
            }
        )
    return normalized


def _safe_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_used_keywords(raw: object) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LLMStructuredOutputError("used_keywords must be an object when provided.")
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        field = _safe_string(key)
        evidence = _safe_string(value)
        if field and evidence:
            normalized[field] = evidence
    return normalized


def _has_semantic_signal(payload: dict[str, Any]) -> bool:
    for key in SEMANTIC_PRESENCE_FIELDS:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict) and not value:
            continue
        return True
    return False


def _partition_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    highlighted = [item for item in items if bool(item.get("is_highlighted"))]
    if highlighted:
        highlighted_keys = {(item["name"], item["amount"]) for item in highlighted}
        non_contributing = [item for item in items if (item["name"], item["amount"]) not in highlighted_keys]
        return highlighted, non_contributing
    return list(items), []


def normalize_llm_payload(
    *,
    receipt_filename: str,
    payload: dict[str, Any],
    deterministic_base: dict[str, Any],
) -> dict[str, Any]:
    """Normalize LLM payload into the current extraction schema."""
    if not isinstance(payload, dict):
        raise LLMStructuredOutputError("LLM payload must be a JSON object.")
    if not _has_semantic_signal(payload):
        raise LLMStructuredOutputError("LLM payload has no semantic extraction signal.")

    merged = deepcopy(deterministic_base)
    merged["filename"] = receipt_filename

    for key in ("document_type", "merchant_name", "transaction_date", "transaction_type", "currency"):
        if key in payload:
            value = _safe_string(payload.get(key))
            if value:
                merged[key] = value

    current_type = _safe_string(merged.get("transaction_type"))
    if current_type:
        merged["transaction_type"] = normalize_transaction_type(
            current_type,
            context_text=f"{_safe_string(merged.get('merchant_name'))} {_safe_string(merged.get('document_type'))}",
            default="",
        )
    else:
        merged["transaction_type"] = ""

    for key in NUMERIC_FIELDS:
        if key in payload:
            merged[key] = _to_float(payload.get(key))

    if "used_keywords" in payload:
        merged["used_keywords"] = _normalize_used_keywords(payload.get("used_keywords"))

    line_items_payload = payload.get("line_items", None)
    contributing_payload = payload.get("contributing_items", None)
    noncontributing_payload = payload.get("noncontributing_items", None)

    if contributing_payload is not None or noncontributing_payload is not None:
        contributing_items = _normalize_items(contributing_payload, "contributing_items")
        noncontributing_items = _normalize_items(noncontributing_payload, "noncontributing_items")
        line_items = contributing_items + noncontributing_items
    elif line_items_payload is not None:
        line_items = _normalize_items(line_items_payload, "line_items")
        contributing_items, noncontributing_items = _partition_items(line_items)
    else:
        line_items = list(merged.get("line_items", []))
        contributing_items = list(merged.get("contributing_items", []))
        noncontributing_items = list(merged.get("noncontributing_items", []))

    merged["line_items"] = line_items
    merged["contributing_items"] = contributing_items
    merged["noncontributing_items"] = noncontributing_items
    merged["contributing_items_total"] = round(sum(float(item["amount"]) for item in contributing_items), 2)
    merged["noncontributing_items_total"] = round(sum(float(item["amount"]) for item in noncontributing_items), 2)
    merged["contributing_items_count"] = len(contributing_items)
    merged["noncontributing_items_count"] = len(noncontributing_items)
    merged["has_highlighted_contributions"] = any(
        bool(item.get("is_highlighted")) for item in contributing_items
    )

    confidence_raw = payload.get("confidence")
    if confidence_raw is not None:
        confidence_value = _to_float(confidence_raw)
        if confidence_value is not None:
            merged["confidence"] = max(0.0, min(1.0, round(confidence_value, 4)))

    needs_review_value = _to_bool(payload.get("needs_review"))
    if needs_review_value is not None:
        merged["needs_review"] = needs_review_value

    return merged
