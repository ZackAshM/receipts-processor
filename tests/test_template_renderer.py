from __future__ import annotations

import pytest

from receipt_processor.io.template_loader import TemplateHints
from receipt_processor.io.template_renderer import (
    infer_required_review_fields,
    normalize_date_string,
    render_rows_from_model_template,
)


def test_template_renderer_renders_keywords_and_operations() -> None:
    model_columns = ["Date", "Description", "Amt Claimed (USD)"]
    model_rows = [
        {
            "Date": "{{transaction_date}}",
            "Description": "{{description}}",
            "Amt Claimed (USD)": "{{true_expense}}",
        },
        {
            "Date": "",
            "Description": "Total:",
            "Amt Claimed (USD)": "<total_expenses>",
        },
    ]
    receipt_keywords = [
        {"transaction_date": "2026-04-25", "description": "Food - Cafe", "true_expense": 12.34},
        {"transaction_date": "2026-04-26", "description": "Food - Grill", "true_expense": 10.00},
    ]
    operations = {"total_expenses": 22.34}
    hints = TemplateHints(date_output_format="%Y %m %d", currency_symbol="$")

    rows, unknown_keywords, unknown_operations = render_rows_from_model_template(
        model_columns=model_columns,
        model_rows=model_rows,
        receipt_keyword_rows=receipt_keywords,
        operation_values=operations,
        template_hints=hints,
    )

    assert unknown_keywords == set()
    assert unknown_operations == set()
    assert len(rows) == 3
    assert rows[0]["Date"] == "2026 04 25"
    assert rows[0]["Amt Claimed (USD)"] == "$12.34"
    assert rows[1]["Date"] == "2026 04 26"
    assert rows[2]["Description"] == "Total:"
    assert rows[2]["Amt Claimed (USD)"] == "$22.34"


def test_template_renderer_requires_keyword_placeholders_when_receipts_exist() -> None:
    model_columns = ["Date", "Description", "Amt Claimed (USD)"]
    model_rows: list[dict[str, str]] = []
    receipt_keywords = [
        {"transaction_date": "2026-04-25", "description": "Food - Cafe", "true_expense": 12.34},
    ]
    hints = TemplateHints(date_output_format="%Y %m %d", currency_symbol="$")

    with pytest.raises(ValueError, match="Alias-based column mapping is no longer supported"):
        render_rows_from_model_template(
            model_columns=model_columns,
            model_rows=model_rows,
            receipt_keyword_rows=receipt_keywords,
            operation_values={},
            template_hints=hints,
        )


def test_template_renderer_supports_operation_rows_with_no_receipts() -> None:
    model_columns = ["Label", "Value"]
    model_rows = [
        {"Label": "Total", "Value": "<total_expenses>"},
    ]
    rows, unknown_keywords, unknown_operations = render_rows_from_model_template(
        model_columns=model_columns,
        model_rows=model_rows,
        receipt_keyword_rows=[],
        operation_values={"total_expenses": 0.0},
        template_hints=TemplateHints(currency_symbol="$"),
    )

    assert unknown_keywords == set()
    assert unknown_operations == set()
    assert rows == [{"Label": "Total", "Value": "$0.00"}]


def test_infer_required_review_fields_from_keyword_templates() -> None:
    model_columns = ["Date", "Description", "Amt Claimed (USD)"]
    model_rows = [
        {
            "Date": "{{transaction_date}}",
            "Description": "{{description}}",
            "Amt Claimed (USD)": "{{true_expense}}",
        }
    ]

    required = infer_required_review_fields(model_columns=model_columns, model_rows=model_rows)
    assert required == {"date", "vendor", "expense_type", "amount"}


def test_infer_required_review_fields_without_keyword_placeholders_is_empty() -> None:
    model_columns = ["Amt Claimed (USD)"]
    model_rows: list[dict[str, str]] = []

    required = infer_required_review_fields(model_columns=model_columns, model_rows=model_rows)
    assert required == set()


def test_normalize_date_string_handles_diverse_datetime_inputs() -> None:
    output_format = "%Y/%m/%d"
    assert normalize_date_string("08/18/25 9:53:20 AM", output_format) == "2025/08/18"
    assert normalize_date_string("Date: 8/22/2025, 3:42 AM", output_format) == "2025/08/22"
    assert normalize_date_string("22AUG25", output_format) == "2025/08/22"
    assert normalize_date_string("DATE B/22/25", output_format) == "2025/08/22"
