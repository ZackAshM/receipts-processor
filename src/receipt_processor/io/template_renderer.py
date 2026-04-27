"""Model-driven keyword/operation template rendering."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from receipt_processor.io.template_loader import TemplateHints

KEYWORD_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
OPERATION_TOKEN_RE = re.compile(r"<\s*([a-zA-Z0-9_]+)\s*>")

SUPPORTED_TEMPLATE_KEYWORDS = {
    "filename",
    "document_type",
    "merchant_name",
    "transaction_date",
    "transaction_type",
    "currency",
    "line_items",
    "contributing_items",
    "noncontributing_items",
    "contributing_items_total",
    "noncontributing_items_total",
    "contributing_items_count",
    "noncontributing_items_count",
    "subtotal",
    "tax",
    "tip",
    "service_charge",
    "pre_tip_total",
    "amount_paid",
    "used_keywords",
    "confidence",
    "needs_review",
    "highlight_detection_available",
    "has_highlighted_contributions",
    "raw_text_length",
    "true_expense",
    "receipt_expense",
    "receipt_amount_if_different",
    "description",
    "contributing_item_names",
    "noncontributing_item_names",
    "contributing_items_json",
    "noncontributing_items_json",
    "used_keywords_json",
    "notes_files",
}

SUPPORTED_TEMPLATE_OPERATIONS = {
    "total_expenses",
    "total_receipt_expenses",
    "total_contributing_items",
    "total_noncontributing_items",
    "receipt_count",
    "review_count",
}

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

DATE_PARSE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m.%d.%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%m.%d.%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d.%m.%y",
    "%Y%m%d",
    "%d%b%Y",
    "%d%b%y",
    "%d%B%Y",
    "%d%B%y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d-%B-%Y",
    "%d-%B-%y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b, %Y",
    "%d %B, %Y",
    "%Y-%m-%d %I:%M:%S %p",
    "%Y-%m-%d %I:%M %p",
    "%Y/%m/%d %I:%M:%S %p",
    "%Y/%m/%d %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%y %I:%M:%S %p",
    "%m/%d/%y %I:%M %p",
    "%m-%d-%Y %I:%M:%S %p",
    "%m-%d-%Y %I:%M %p",
    "%m-%d-%y %I:%M:%S %p",
    "%m-%d-%y %I:%M %p",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
)

DATE_CANDIDATE_PATTERNS = (
    re.compile(
        r"\b\d{4}[./-]\d{1,2}[./-]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)?\b"
    ),
    re.compile(
        r"\b[0-9A-Za-z]{1,2}[./-][0-9A-Za-z]{1,2}[./-][0-9A-Za-z]{2,4}"
        r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)?\b"
    ),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
        r"|January|February|March|April|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
        r"|January|February|March|April|June|July|August|September|October|November|December)"
        r",?\s+\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}[A-Za-z]{3}\d{2,4}\b"),
    re.compile(r"\b\d{8}\b"),
)

OCR_DIGIT_TRANSLATION = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "S": "5",
        "s": "5",
        "B": "8",
    }
)

MONEY_REVIEW_KEYS = {
    "amount",
    "amount_paid",
    "true_expense",
    "receipt_expense",
    "receipt_amount_if_different",
    "subtotal",
    "tax",
    "tip",
    "service_charge",
    "pre_tip_total",
    "contributing_items_total",
    "noncontributing_items_total",
}


def _keyword_to_review_fields(keyword: str) -> set[str]:
    normalized = _normalize_label(keyword)
    if normalized in {"transaction_date", "date"}:
        return {"date"}
    if normalized in {"transaction_type", "expense_type"}:
        return {"expense_type"}
    if normalized in {"merchant_name", "vendor"}:
        return {"vendor"}
    if normalized == "description":
        return {"vendor", "expense_type"}
    if normalized in MONEY_REVIEW_KEYS:
        return {"amount"}
    return set()


def infer_required_review_fields(
    model_columns: list[str],
    model_rows: list[dict[str, str]],
) -> set[str]:
    """Infer which review fields can affect final model output."""
    _ = model_columns
    required: set[str] = set()

    for row in model_rows:
        for value in row.values():
            text = str(value or "")
            for match in KEYWORD_TOKEN_RE.finditer(text):
                required.update(_keyword_to_review_fields(match.group(1)))
    return required


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _clean_date_candidate(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"^[A-Za-z][A-Za-z\s]{0,24}:\s*", "", cleaned)
    cleaned = re.sub(r"\bAT\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\b(?:UTC|GMT|[ECMP][SD]T|PST|PDT|CST|CDT|MST|MDT|EST|EDT)$", "", cleaned).strip()
    return cleaned


def _normalize_ocr_digits(value: str) -> str:
    token = value.strip()
    match = re.match(
        r"^(?P<date>[0-9A-Za-z]{1,2}[./-][0-9A-Za-z]{1,2}[./-][0-9A-Za-z]{2,4})"
        r"(?P<time>\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)?$",
        token,
    )
    if not match:
        return token
    date_part = match.group("date")
    time_part = match.group("time") or ""
    separator = next((sep for sep in ("/", "-", ".") if sep in date_part), "/")
    normalized_parts = [part.translate(OCR_DIGIT_TRANSLATION) for part in date_part.split(separator)]
    return f"{separator.join(normalized_parts)}{time_part}".strip()


def _parse_datetime_candidate(value: str) -> datetime | None:
    for fmt in DATE_PARSE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _iter_date_candidates(raw_value: str) -> list[str]:
    candidates: list[str] = [raw_value]
    for pattern in DATE_CANDIDATE_PATTERNS:
        for match in pattern.finditer(raw_value):
            candidate = match.group(0).strip()
            if candidate:
                candidates.append(candidate)

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _format_date(value: str, output_format: str) -> str:
    for raw_candidate in _iter_date_candidates(value):
        for candidate in (_clean_date_candidate(raw_candidate), _normalize_ocr_digits(_clean_date_candidate(raw_candidate))):
            parsed = _parse_datetime_candidate(candidate)
            if parsed is not None:
                return parsed.strftime(output_format)
    return value


def normalize_date_string(value: object, output_format: str) -> str:
    """Normalize an arbitrary date string to a target output format when possible."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime(output_format)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).strftime(output_format)
    text = str(value).strip()
    if not text:
        return ""
    return _format_date(text, output_format)


def _format_value(field: str, value: object, hints: TemplateHints) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if field == "transaction_date":
        return normalize_date_string(value, hints.date_output_format)
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


def has_keyword_placeholders(model_rows: list[dict[str, str]]) -> bool:
    """Return True when any model row contains at least one {{keyword}} token."""
    return any(_row_has_keyword_tokens(row) for row in model_rows)


def collect_template_tokens(model_rows: list[dict[str, str]]) -> tuple[set[str], set[str]]:
    """Return all keyword and operation tokens referenced in a model template."""
    keywords: set[str] = set()
    operations: set[str] = set()
    for row in model_rows:
        for value in row.values():
            text = str(value or "")
            for match in KEYWORD_TOKEN_RE.finditer(text):
                keywords.add(match.group(1))
            for match in OPERATION_TOKEN_RE.finditer(text):
                operations.add(match.group(1))
    return keywords, operations


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

    has_keyword_rows = has_keyword_placeholders(model_rows)

    if not model_rows:
        if receipt_keyword_rows:
            raise ValueError(
                "Model template must include at least one {{keyword}} placeholder row. "
                "Alias-based column mapping is no longer supported."
            )
        return [], unknown_keywords, unknown_operations

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
        raise ValueError(
            "Model template must include at least one {{keyword}} placeholder row. "
            "Alias-based column mapping is no longer supported."
        )

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
