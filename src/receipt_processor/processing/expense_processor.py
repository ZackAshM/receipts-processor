"""Deterministic processing of structured extraction output."""

from __future__ import annotations

import json
from typing import Any


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


def process_structured_data(extracted: dict[str, Any]) -> dict[str, Any]:
    """Add processed fields and keyword-ready values for template rendering."""
    subtotal = _round_money(extracted.get("subtotal"))
    tax = _round_money(extracted.get("tax"))
    tip = _round_money(extracted.get("tip"))
    service_charge = _round_money(extracted.get("service_charge"))
    pre_tip_total = _round_money(extracted.get("pre_tip_total"))
    amount_paid = _round_money(extracted.get("amount_paid"))

    contributing_total = _round_money(extracted.get("contributing_items_total")) or 0.0
    noncontributing_total = _round_money(extracted.get("noncontributing_items_total")) or 0.0

    if pre_tip_total is None and subtotal is not None:
        pre_tip_total = _safe_sum([subtotal, tax, service_charge])

    if amount_paid is None:
        amount_paid = _round_money(_safe_sum([pre_tip_total, tip])) if pre_tip_total is not None else None
    if amount_paid is None:
        amount_paid = _round_money(_safe_sum([contributing_total, noncontributing_total]))

    if subtotal is not None or tax is not None or tip is not None or service_charge is not None:
        if subtotal is None and amount_paid is not None:
            subtotal = _round_money(amount_paid - _safe_sum([tax, tip, service_charge]))
        true_expense = _safe_sum([subtotal, tax, tip, service_charge]) - noncontributing_total
    else:
        if contributing_total > 0:
            true_expense = contributing_total
        elif amount_paid is not None:
            true_expense = amount_paid
        else:
            true_expense = 0.0
    true_expense = round(true_expense, 2)

    receipt_expense = _round_money(amount_paid) or 0.0
    receipt_amount_if_different: float | None = None
    if abs(true_expense - receipt_expense) > 0.009:
        receipt_amount_if_different = receipt_expense

    transaction_type = str(extracted.get("transaction_type", "")).strip() or "Other"
    merchant_name = str(extracted.get("merchant_name", "")).strip()
    description = f"{transaction_type} - {merchant_name}".strip(" -")

    contributing_items = extracted.get("contributing_items", [])
    noncontributing_items = extracted.get("noncontributing_items", [])

    needs_review = _to_bool(extracted.get("needs_review", False))
    confidence = extracted.get("confidence")
    if confidence is None:
        confidence = 0.0

    return {
        "true_expense": true_expense,
        "receipt_expense": receipt_expense,
        "receipt_amount_if_different": receipt_amount_if_different,
        "description": description,
        "subtotal": subtotal,
        "tax": tax,
        "tip": tip,
        "service_charge": service_charge,
        "pre_tip_total": pre_tip_total,
        "amount_paid": amount_paid,
        "contributing_items_total": _round_money(contributing_total),
        "noncontributing_items_total": _round_money(noncontributing_total),
        "contributing_items_count": int(extracted.get("contributing_items_count", len(contributing_items))),
        "noncontributing_items_count": int(
            extracted.get("noncontributing_items_count", len(noncontributing_items))
        ),
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
