from pathlib import Path

from receipt_processor.extraction.schema_mapper import map_to_model_columns
from receipt_processor.io.template_loader import infer_template_hints, load_model_columns
from receipt_processor.quality.validation import validate_expense_record


def test_template_hints_infer_expected_model_shape() -> None:
    model = Path("models/model.csv")
    example = Path("models/example.csv")

    columns = load_model_columns(model)
    hints = infer_template_hints(model, example)

    assert "Date" in columns
    assert hints.date_column == "Date"
    assert hints.description_column == "Description"
    assert hints.amount_column == "Amt Claimed (USD)"
    assert hints.date_output_format == "%Y %m %d"
    assert hints.currency_symbol == "$"


def test_schema_mapper_uses_template_hints() -> None:
    model = Path("models/model.csv")
    example = Path("models/example.csv")

    columns = load_model_columns(model)
    hints = infer_template_hints(model, example)

    parsed = {
        "date": "2025-06-25",
        "vendor": "Lyft",
        "amount": "54.91",
        "expense_type": "Transportation",
    }
    row = map_to_model_columns(parsed, columns, template_hints=hints)

    assert row["Date"] == "2025 06 25"
    assert row["Description"] == "Transportation - Lyft"
    assert row["Amt Claimed (USD)"] == "$54.91"


def test_validation_checks_required_alias_fields() -> None:
    good_record = {
        "Date": "2025 06 25",
        "Description": "Food - Chilis",
        "Amt Claimed (USD)": "$45.94",
    }
    assert validate_expense_record(good_record) == (True, [])

    bad_record = {
        "Date": "",
        "Description": "",
        "Amt Claimed (USD)": "",
    }
    valid, errors = validate_expense_record(bad_record)
    assert valid is False
    assert len(errors) == 3
