from __future__ import annotations

import csv
from pathlib import Path

import pytest

from receipt_processor.pipeline import run_pipeline


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_pipeline_supports_contract_template_without_legacy_required_columns(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "receipt.png").write_bytes(b"not-an-image")
    (inbox / "receipt_notes.txt").write_text(
        "vendor: Cafe\n"
        "date: 2026-04-26\n"
        "amount: 10.50\n"
        "expense_type: Food\n",
        encoding="utf-8",
    )

    model_file = tmp_path / "model.csv"
    model_file.write_text(
        "Merchant Label,Claimed Amount\n"
        "{{merchant_name}},{{true_expense}}\n"
        "TOTAL,<total_expenses>\n",
        encoding="utf-8",
    )

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Merchant Label,Claimed Amount\n"
        "Cafe,10.50\n",
        encoding="utf-8",
    )

    output_file = tmp_path / "Expenses.csv"
    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=tmp_path / "logs",
    )

    rows = _read_csv_rows(output_file)
    assert rows[0]["Merchant Label"] == "Cafe"
    assert rows[0]["Claimed Amount"] == "10.50"
    assert rows[1]["Merchant Label"] == "TOTAL"
    assert rows[1]["Claimed Amount"] == "10.50"

    exceptions_file = output_file.with_name("Expenses_exceptions.csv")
    assert not exceptions_file.exists() or _read_csv_rows(exceptions_file) == []


def test_pipeline_requires_keyword_placeholders_in_model_template(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "receipt.png").write_bytes(b"not-an-image")
    (inbox / "receipt_notes.txt").write_text(
        "vendor: Cafe\n"
        "date: 2026-04-26\n"
        "amount: 10.50\n"
        "expense_type: Food\n",
        encoding="utf-8",
    )

    model_file = tmp_path / "model.csv"
    model_file.write_text("Date,Description,Amt Claimed (USD)\n", encoding="utf-8")

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "2026 04 26,Food - Cafe,$10.50\n",
        encoding="utf-8",
    )

    output_file = tmp_path / "Expenses.csv"
    with pytest.raises(ValueError, match="Alias-based column mapping is no longer supported"):
        run_pipeline(
            input_dir=inbox,
            model_file=model_file,
            example_file=example_file,
            output_file=output_file,
            log_dir=tmp_path / "logs",
        )
