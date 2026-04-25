"""Map parsed fields into target model columns."""

from __future__ import annotations

import re
from datetime import datetime

from receipt_processor.io.template_loader import TemplateHints

DATE_INPUT_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y")


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _find_column(columns: list[str], candidates: tuple[str, ...]) -> str:
    normalized_to_original = {_normalize(col): col for col in columns}
    for candidate in candidates:
        for norm, original in normalized_to_original.items():
            if candidate in norm:
                return original
    return ""


def _format_date(date_value: str, output_format: str) -> str:
    if not date_value:
        return ""
    for fmt in DATE_INPUT_FORMATS:
        try:
            parsed = datetime.strptime(date_value, fmt)
            return parsed.strftime(output_format)
        except ValueError:
            continue
    return date_value


def _to_amount_string(amount: str, currency_symbol: str) -> str:
    if not amount:
        return ""
    normalized = amount.replace(",", "").replace("$", "").strip()
    try:
        numeric = float(normalized)
    except ValueError:
        return amount
    rendered = f"{numeric:.2f}"
    if currency_symbol:
        return f"{currency_symbol}{rendered}"
    return rendered


def map_to_model_columns(
    parsed_fields: dict[str, str],
    model_columns: list[str],
    template_hints: TemplateHints | None = None,
) -> dict[str, str]:
    """Create a model-aligned output record from canonical parsed fields."""
    hints = template_hints or TemplateHints()
    record: dict[str, str] = {column: "" for column in model_columns}

    date_col = hints.date_column or _find_column(model_columns, ("date",))
    description_col = hints.description_column or _find_column(
        model_columns, ("description", "memo", "details")
    )
    amount_col = hints.amount_column or _find_column(
        model_columns, ("amt claimed", "amount", "total")
    )
    receipt_amount_col = hints.receipt_amount_column or _find_column(
        model_columns, ("receipt amt", "receipt amount")
    )

    expense_type = parsed_fields.get("expense_type", "").strip() or "Other"
    vendor = parsed_fields.get("vendor", "").strip()
    description = parsed_fields.get("description", "").strip()
    if not description and vendor:
        description = f"{expense_type} - {vendor}"

    date_value = _format_date(parsed_fields.get("date", "").strip(), hints.date_output_format)
    amount_value = _to_amount_string(parsed_fields.get("amount", "").strip(), hints.currency_symbol)
    receipt_amount_value = _to_amount_string(
        parsed_fields.get("receipt_amount", "").strip(),
        hints.currency_symbol,
    )

    if date_col:
        record[date_col] = date_value
    if description_col:
        record[description_col] = description
    if amount_col:
        record[amount_col] = amount_value
    if receipt_amount_col:
        # Keep empty when not provided or when equal to claimed amount.
        if receipt_amount_value and receipt_amount_value != amount_value:
            record[receipt_amount_col] = receipt_amount_value

    # Backfill any exact-name columns that exist outside standard aliases.
    for key, value in parsed_fields.items():
        if key in record and not record[key]:
            record[key] = value

    extras = {
        key: value
        for key, value in parsed_fields.items()
        if key not in record and value not in (None, "")
    }
    if extras:
        record["_extras"] = str(extras)

    return record
