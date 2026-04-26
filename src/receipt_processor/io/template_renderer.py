"""Model-driven keyword/operation template rendering."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from receipt_processor.io.template_loader import TemplateHints

KEYWORD_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
OPERATION_TOKEN_RE = re.compile(r"<\s*([a-zA-Z0-9_]+)\s*>")

MONEY_FIELDS = {
    "subtotal",
    "tax",
    "tip",
    "service_charge",
    "pre_tip_total",
    "amount_paid",
    "true_expense",
    "receipt_expense",
    "receipt_amount_if_different",
    "contributing_items_total",
    "noncontributing_items_total",
    "total_expenses",
    "total_receipt_expenses",
    "total_contributing_items",
    "total_noncontributing_items",
}

DATE_INPUT_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y")

COLUMN_ALIAS_MAP = {
    "date": "transaction_date",
    "description": "description",
    "amt_claimed_usd": "true_expense",
    "amount_claimed": "true_expense",
    "amount": "true_expense",
    "receipt_amt_if_different_from_amt_claimed": "receipt_amount_if_different",
    "receipt_amount_if_different_from_amount_claimed": "receipt_amount_if_different",
    "receipt_amount": "receipt_expense",
}


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _format_date(value: str, output_format: str) -> str:
    for fmt in DATE_INPUT_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime(output_format)
        except ValueError:
            continue
    return value


def _format_value(field: str, value: object, hints: TemplateHints) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if field == "transaction_date":
        date_text = str(value).strip()
        return _format_date(date_text, hints.date_output_format) if date_text else ""
    if isinstance(value, (int, float)):
        if field in MONEY_FIELDS:
            amount = f"{float(value):.2f}"
            return f"{hints.currency_symbol}{amount}" if hints.currency_symbol else amount
        if field.endswith("_count"):
            return str(int(value))
        return str(value)
    return str(value)


def _render_cell(
    template_value: str,
    keyword_values: dict[str, object],
    operation_values: dict[str, object],
    hints: TemplateHints,
    unknown_keywords: set[str],
    unknown_operations: set[str],
) -> str:
    rendered = template_value

    def replace_keyword(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in keyword_values:
            unknown_keywords.add(key)
            return ""
        return _format_value(key, keyword_values.get(key), hints)

    def replace_operation(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in operation_values:
            unknown_operations.add(key)
            return ""
        return _format_value(key, operation_values.get(key), hints)

    rendered = KEYWORD_TOKEN_RE.sub(replace_keyword, rendered)
    rendered = OPERATION_TOKEN_RE.sub(replace_operation, rendered)
    return rendered


def _row_has_keyword_tokens(row: dict[str, str]) -> bool:
    return any(KEYWORD_TOKEN_RE.search(str(value or "")) for value in row.values())


def _row_has_operation_tokens(row: dict[str, str]) -> bool:
    return any(OPERATION_TOKEN_RE.search(str(value or "")) for value in row.values())


def map_columns_from_keywords(
    model_columns: list[str],
    keyword_values: dict[str, object],
    template_hints: TemplateHints | None = None,
) -> dict[str, str]:
    """Best-effort column mapping when explicit keyword placeholders are absent."""
    hints = template_hints or TemplateHints()
    normalized_keyword_map = {
        _normalize_label(str(key)): str(key)
        for key in keyword_values.keys()
    }
    row: dict[str, str] = {}
    for column in model_columns:
        normalized = _normalize_label(column)
        alias_key = COLUMN_ALIAS_MAP.get(normalized)
        if alias_key and alias_key in keyword_values:
            key = alias_key
        else:
            key = normalized_keyword_map.get(normalized, alias_key or normalized)
        value = keyword_values.get(key)
        row[column] = _format_value(key, value, hints)
    return row


def render_rows_from_model_template(
    model_columns: list[str],
    model_rows: list[dict[str, str]],
    receipt_keyword_rows: list[dict[str, object]],
    operation_values: dict[str, object],
    template_hints: TemplateHints | None = None,
) -> tuple[list[dict[str, str]], set[str], set[str]]:
    """Render output rows from model template rows using keyword/operation tokens."""
    hints = template_hints or TemplateHints()
    unknown_keywords: set[str] = set()
    unknown_operations: set[str] = set()

    has_keyword_rows = any(_row_has_keyword_tokens(row) for row in model_rows)

    if not model_rows:
        if not receipt_keyword_rows:
            return [], unknown_keywords, unknown_operations
        # Header-only model fallback.
        rows = [map_columns_from_keywords(model_columns, receipt_values, hints) for receipt_values in receipt_keyword_rows]
        return rows, unknown_keywords, unknown_operations

    if not receipt_keyword_rows:
        # Keep operation-only templates renderable when no receipts are accepted.
        if has_keyword_rows:
            return [], unknown_keywords, unknown_operations
        rendered_rows: list[dict[str, str]] = []
        empty_values: dict[str, object] = {}
        for template_row in model_rows:
            has_ops = _row_has_operation_tokens(template_row)
            rendered: dict[str, str] = {}
            for column in model_columns:
                template_value = str(template_row.get(column, "") or "")
                rendered[column] = _render_cell(
                    template_value=template_value,
                    keyword_values=empty_values,
                    operation_values=operation_values if has_ops else {},
                    hints=hints,
                    unknown_keywords=unknown_keywords,
                    unknown_operations=unknown_operations,
                )
            rendered_rows.append(rendered)
        return rendered_rows, unknown_keywords, unknown_operations

    if not has_keyword_rows:
        rows = [map_columns_from_keywords(model_columns, receipt_values, hints) for receipt_values in receipt_keyword_rows]
        return rows, unknown_keywords, unknown_operations

    rendered_rows: list[dict[str, str]] = []
    default_values = receipt_keyword_rows[0]
    for template_row in model_rows:
        has_keywords = _row_has_keyword_tokens(template_row)
        has_ops = _row_has_operation_tokens(template_row)

        candidate_values = receipt_keyword_rows if has_keywords else [default_values]
        for keyword_values in candidate_values:
            rendered: dict[str, str] = {}
            for column in model_columns:
                template_value = str(template_row.get(column, "") or "")
                rendered[column] = _render_cell(
                    template_value=template_value,
                    keyword_values=keyword_values,
                    operation_values=operation_values if has_ops else {},
                    hints=hints,
                    unknown_keywords=unknown_keywords,
                    unknown_operations=unknown_operations,
                )
            rendered_rows.append(rendered)
        if not has_keywords:
            # Literal and/or operation row should be emitted once.
            continue
    return rendered_rows, unknown_keywords, unknown_operations
