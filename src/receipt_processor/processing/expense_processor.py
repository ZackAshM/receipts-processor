"""Deterministic processing of structured extraction output."""

from __future__ import annotations

import json
from typing import Any

from receipt_processor.extraction.transaction_type import normalize_transaction_type

NONCONTRIBUTING_ADJUSTMENT_TOKENS = (
    "tax",
    "tip",
    "gratuity",
    "service",
    "fee",
    "surcharge",
    "charge",
    "credit",
    "discount",
    "vat",
)


def _round_money(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _safe_sum(values: list[float | int | None]) -> float:
    total = 0.0
    for value in values:
        if value is None:
            continue
        total += float(value)
    return round(total, 2)


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "yes", "on"}
    return bool(value)


def _item_amount(item: object) -> float | None:
    if not isinstance(item, dict):
        return None
    value = item.get("amount")
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _sum_item_amounts(items: list[dict[str, Any]]) -> float:
    return _safe_sum([_item_amount(item) for item in items])


def _normalize_line_items(raw_items: object) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        amount = _item_amount(item)
        if not name or amount is None:
            continue
        normalized.append(
            {
                "name": name,
                "amount": amount,
                "is_highlighted": bool(_to_bool(item.get("is_highlighted", False))),
                "source": str(item.get("source", "")).strip(),
            }
        )
    return normalized


def _fallback_legacy_line_items(extracted: dict[str, Any]) -> list[dict[str, Any]]:
    contributing = _normalize_line_items(extracted.get("contributing_items", []))
    noncontributing = _normalize_line_items(extracted.get("noncontributing_items", []))
    return contributing + noncontributing


def _partition_line_items(
    line_items: list[dict[str, Any]],
    *,
    highlight_detection_available: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    if not highlight_detection_available:
        return list(line_items), [], False
    highlighted = [item for item in line_items if bool(item.get("is_highlighted"))]
    if highlighted:
        noncontributing = [item for item in line_items if not bool(item.get("is_highlighted"))]
        return highlighted, noncontributing, True
    return list(line_items), [], False


def _looks_like_adjustment_item(name: str) -> bool:
    lowered = name.strip().lower()
    return any(token in lowered for token in NONCONTRIBUTING_ADJUSTMENT_TOKENS)


def _sum_effective_noncontributing(items: list[dict[str, Any]]) -> float:
    effective: list[float | None] = []
    for item in items:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        if _looks_like_adjustment_item(name):
            # Taxes/tips/fees/credits are frequently misclassified by semantic extraction.
            # We do not treat them as reducing true expense unless stronger evidence exists.
            continue
        effective.append(_item_amount(item))
    return _safe_sum(effective)


def process_structured_data(extracted: dict[str, Any]) -> dict[str, Any]:
    """Add processed fields and keyword-ready values for template rendering."""
    subtotal = _round_money(extracted.get("subtotal"))
    tax = _round_money(extracted.get("tax"))
    tip = _round_money(extracted.get("tip"))
    service_charge = _round_money(extracted.get("service_charge"))
    pre_tip_total = _round_money(extracted.get("pre_tip_total"))
    amount_paid = _round_money(extracted.get("amount_paid"))

    line_items = _normalize_line_items(extracted.get("line_items", []))
    if not line_items:
        # Backward compatibility for older extraction payloads.
        line_items = _fallback_legacy_line_items(extracted)

    highlight_detection_available = bool(_to_bool(extracted.get("highlight_detection_available", False)))
    contributing_items, noncontributing_items, has_highlighted_contributions = _partition_line_items(
        line_items,
        highlight_detection_available=highlight_detection_available,
    )
    contributing_total = _round_money(_sum_item_amounts(contributing_items)) or 0.0
    noncontributing_total = _round_money(_sum_item_amounts(noncontributing_items)) or 0.0
    effective_noncontributing_total = _round_money(_sum_effective_noncontributing(noncontributing_items)) or 0.0

    if pre_tip_total is None and subtotal is not None:
        pre_tip_total = _safe_sum([subtotal, tax, service_charge])

    if amount_paid is None:
        amount_paid = _round_money(_safe_sum([pre_tip_total, tip])) if pre_tip_total is not None else None
    if amount_paid is None:
        amount_paid = _round_money(_safe_sum([contributing_total, noncontributing_total]))

    has_component_values = subtotal is not None or tax is not None or tip is not None or service_charge is not None
    component_total = _round_money(_safe_sum([subtotal, tax, tip, service_charge])) if has_component_values else None

    if has_component_values:
        if subtotal is None and amount_paid is not None:
            subtotal = _round_money(amount_paid - _safe_sum([tax, tip, service_charge]))
        component_total = _round_money(_safe_sum([subtotal, tax, tip, service_charge]))
        true_expense = (component_total or 0.0) - effective_noncontributing_total
    else:
        if contributing_total > 0:
            true_expense = contributing_total
        elif amount_paid is not None:
            true_expense = amount_paid
        else:
            true_expense = 0.0
    true_expense = round(true_expense, 2)

    line_items_total = _round_money(_safe_sum([contributing_total, noncontributing_total]))
    if amount_paid is not None:
        component_diff = abs((component_total or 0.0) - amount_paid) if component_total is not None else None
        line_items_match_amount = line_items_total is not None and abs(line_items_total - amount_paid) <= 0.05
        if (
            effective_noncontributing_total <= 0.009
            and component_total is not None
            and component_diff is not None
            and component_diff <= 0.75
        ):
            true_expense = round(amount_paid, 2)
        elif (
            effective_noncontributing_total <= 0.009
            and line_items_match_amount
            and (component_diff is None or component_diff > 0.5)
        ):
            true_expense = round(amount_paid, 2)

    receipt_expense = _round_money(amount_paid) or 0.0
    receipt_amount_if_different: float | None = None
    if abs(true_expense - receipt_expense) > 0.009:
        receipt_amount_if_different = receipt_expense

    transaction_type = normalize_transaction_type(
        str(extracted.get("transaction_type", "")).strip(),
        context_text=str(extracted.get("merchant_name", "")).strip(),
    )
    merchant_name = str(extracted.get("merchant_name", "")).strip()
    description = f"{transaction_type} - {merchant_name}".strip(" -")

    needs_review = _to_bool(extracted.get("needs_review", False))
    confidence = extracted.get("confidence")
    if confidence is None:
        confidence = 0.0

    return {
        "true_expense": true_expense,
        "receipt_expense": receipt_expense,
        "receipt_amount_if_different": receipt_amount_if_different,
        "description": description,
        "line_items": line_items,
        "contributing_items": contributing_items,
        "noncontributing_items": noncontributing_items,
        "subtotal": subtotal,
        "tax": tax,
        "tip": tip,
        "service_charge": service_charge,
        "pre_tip_total": pre_tip_total,
        "amount_paid": amount_paid,
        "contributing_items_total": _round_money(contributing_total),
        "noncontributing_items_total": _round_money(noncontributing_total),
        "contributing_items_count": len(contributing_items),
        "noncontributing_items_count": len(noncontributing_items),
        "has_highlighted_contributions": has_highlighted_contributions,
        "highlight_detection_available": highlight_detection_available,
        "contributing_item_names": " | ".join(
            str(item.get("name", "")).strip() for item in contributing_items if str(item.get("name", "")).strip()
        ),
        "noncontributing_item_names": " | ".join(
            str(item.get("name", "")).strip()
            for item in noncontributing_items
            if str(item.get("name", "")).strip()
        ),
        "contributing_items_json": json.dumps(contributing_items, ensure_ascii=True),
        "noncontributing_items_json": json.dumps(noncontributing_items, ensure_ascii=True),
        "used_keywords_json": json.dumps(extracted.get("used_keywords", {}), ensure_ascii=True),
        "confidence": round(float(confidence), 4),
        "needs_review": needs_review,
    }


def summarize_processed_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute run-level operation values from processed receipt rows."""
    total_expenses = _safe_sum([row.get("true_expense") for row in rows])
    total_receipt_expenses = _safe_sum([row.get("receipt_expense") for row in rows])
    total_contributing_items = _safe_sum([row.get("contributing_items_total") for row in rows])
    total_noncontributing_items = _safe_sum([row.get("noncontributing_items_total") for row in rows])
    receipt_count = len(rows)
    review_count = sum(1 for row in rows if _to_bool(row.get("needs_review")))

    return {
        "total_expenses": round(total_expenses, 2),
        "total_receipt_expenses": round(total_receipt_expenses, 2),
        "total_contributing_items": round(total_contributing_items, 2),
        "total_noncontributing_items": round(total_noncontributing_items, 2),
        "receipt_count": receipt_count,
        "review_count": review_count,
    }
