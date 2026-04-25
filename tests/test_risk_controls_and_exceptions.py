from __future__ import annotations

import csv
from pathlib import Path

from receipt_processor.pipeline import run_pipeline
from receipt_processor.quality.exception_queue import export_exception_records


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_exception_export_sanitizes_formula_like_values(tmp_path: Path) -> None:
    out = tmp_path / "exceptions.csv"
    records = [
        {
            "status": "requires_review",
            "details": "=HYPERLINK(\"http://example.com\")",
            "source_file": "+invoice.png",
        }
    ]

    export_exception_records(records, out)
    rows = _read_csv_rows(out)

    assert rows[0]["details"].startswith("'")
    assert rows[0]["source_file"].startswith("'")


def test_pipeline_enforces_low_confidence_threshold_from_config(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "lyft.png").write_bytes(b"not-an-image")
    (inbox / "lyft_notes.txt").write_text(
        "vendor: Lyft\ndate: 2025-06-25\namount: 54.91\nexpense_type: Transportation\n",
        encoding="utf-8",
    )

    model = tmp_path / "model.csv"
    model.write_text(
        "Date,Description,Amt Claimed (USD),Project\n",
        encoding="utf-8",
    )
    example = tmp_path / "example.csv"
    example.write_text(
        "Date,Description,Amt Claimed (USD),Project\n2025 06 25,Transportation - Lyft,$54.91,Alpha\n",
        encoding="utf-8",
    )

    controls = tmp_path / "risk_controls.yaml"
    controls.write_text(
        "controls:\n"
        "  route_low_confidence_to_review: true\n"
        "thresholds:\n"
        "  minimum_auto_accept_confidence: 0.90\n"
        "  require_manual_review_below: 0.80\n",
        encoding="utf-8",
    )

    output = tmp_path / "Expenses.csv"
    run_pipeline(
        input_dir=inbox,
        model_file=model,
        example_file=example,
        output_file=output,
        log_dir=tmp_path / "logs",
        risk_controls_file=controls,
    )

    main_rows = _read_csv_rows(output)
    assert main_rows == []

    exceptions = _read_csv_rows(output.with_name("Expenses_exceptions.csv"))
    assert len(exceptions) == 1
    assert exceptions[0]["issue_type"] == "low_confidence"
    assert "minimum_auto_accept" in exceptions[0]["details"]
    assert exceptions[0]["review_level"] == "required"
