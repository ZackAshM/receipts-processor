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


def test_pipeline_fails_on_unknown_keyword_placeholders(tmp_path: Path) -> None:
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
        "Date,Description,Amt Claimed (USD)\n"
        "{{transaction_date}},{{not_a_supported_keyword}},{{true_expense}}\n",
        encoding="utf-8",
    )

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "2026 04 26,Food - Cafe,$10.50\n",
        encoding="utf-8",
    )
    controls_file = tmp_path / "risk_controls.yaml"
    controls_file.write_text(
        "controls:\n"
        "  route_low_confidence_to_review: false\n"
        "thresholds:\n"
        "  minimum_auto_accept_confidence: 0.0\n"
        "  require_manual_review_below: 0.0\n",
        encoding="utf-8",
    )

    output_file = tmp_path / "Expenses.csv"
    with pytest.raises(ValueError, match="Unknown template tokens detected"):
        run_pipeline(
            input_dir=inbox,
            model_file=model_file,
            example_file=example_file,
            output_file=output_file,
            log_dir=tmp_path / "logs",
            risk_controls_file=controls_file,
        )


def test_pipeline_fails_on_unknown_operation_placeholders(tmp_path: Path) -> None:
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
        "Date,Description,Amt Claimed (USD)\n"
        "{{transaction_date}},{{description}},{{true_expense}}\n"
        "TOTAL,All Receipts,<total_expenses_typo>\n",
        encoding="utf-8",
    )

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "2026 04 26,Food - Cafe,$10.50\n",
        encoding="utf-8",
    )
    controls_file = tmp_path / "risk_controls.yaml"
    controls_file.write_text(
        "controls:\n"
        "  route_low_confidence_to_review: false\n"
        "thresholds:\n"
        "  minimum_auto_accept_confidence: 0.0\n"
        "  require_manual_review_below: 0.0\n",
        encoding="utf-8",
    )

    output_file = tmp_path / "Expenses.csv"
    with pytest.raises(ValueError, match="Unknown template tokens detected"):
        run_pipeline(
            input_dir=inbox,
            model_file=model_file,
            example_file=example_file,
            output_file=output_file,
            log_dir=tmp_path / "logs",
            risk_controls_file=controls_file,
        )


def test_unknown_template_tokens_fail_before_extraction_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "receipt.png").write_bytes(b"not-an-image")

    model_file = tmp_path / "model.csv"
    model_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "{{unknown_keyword}},{{description}},{{true_expense}}\n",
        encoding="utf-8",
    )

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "2026 04 26,Food - Cafe,$10.50\n",
        encoding="utf-8",
    )

    called = {"extract_document": False}

    def _should_not_run(_receipt_path: Path):
        called["extract_document"] = True
        raise AssertionError("extract_document should not run on template preflight failure")

    monkeypatch.setattr("receipt_processor.pipeline.extract_document", _should_not_run)

    with pytest.raises(ValueError, match="Unknown template tokens detected before processing"):
        run_pipeline(
            input_dir=inbox,
            model_file=model_file,
            example_file=example_file,
            output_file=tmp_path / "Expenses.csv",
            log_dir=tmp_path / "logs",
        )

    assert called["extract_document"] is False
