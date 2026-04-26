from __future__ import annotations

import csv
from pathlib import Path

from receipt_processor.extraction.notes_inference import infer_fields_from_notes
from receipt_processor.pipeline import run_pipeline
from receipt_processor.quality.consistency import detect_contradictions, is_null_result


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_infer_fields_from_notes_supports_global_and_receipt_specific(tmp_path: Path) -> None:
    receipt = tmp_path / "trip.png"
    receipt.write_bytes(b"not-an-image")

    (tmp_path / "notes.txt").write_text("vendor: Global Vendor\n", encoding="utf-8")
    (tmp_path / "trip_notes.txt").write_text(
        "date: 2025-06-25\namount: 54.91\nexpense_type: Transportation\n",
        encoding="utf-8",
    )

    fields, matched = infer_fields_from_notes(tmp_path, receipt)

    assert "notes.txt" in matched
    assert "trip_notes.txt" in matched
    assert fields["vendor"] == "Global Vendor"
    assert fields["date"] == "2025-06-25"
    assert fields["amount"] == "54.91"


def test_detect_contradictions_and_null_result() -> None:
    contradictions = detect_contradictions(
        {
            "filename": {"amount": "19.23", "date": "2025-06-24"},
            "notes": {"amount": "20.00", "date": "2025-06-24"},
            "file": {},
        }
    )
    assert any("amount mismatch" in item for item in contradictions)

    assert is_null_result({"vendor": "", "date": "", "amount": ""}) is True
    assert is_null_result({"vendor": "Store", "date": "", "amount": ""}) is False


def test_detect_contradictions_tolerates_filename_noise_tokens() -> None:
    contradictions = detect_contradictions(
        {
            "filename": {"vendor": "Food GreatBasinBakery"},
            "file": {"vendor": "Great Basin Bakery"},
            "notes": {},
        }
    )
    assert not any("vendor mismatch" in item for item in contradictions)


def test_pipeline_uses_notes_for_missing_fields(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    receipt = inbox / "lyft.png"
    receipt.write_bytes(b"not-an-image")
    (inbox / "lyft_notes.txt").write_text(
        "vendor: Lyft\ndate: 2025-06-25\namount: 54.91\nexpense_type: Transportation\n",
        encoding="utf-8",
    )

    output = tmp_path / "Expenses.csv"
    run_pipeline(
        input_dir=inbox,
        model_file=Path("models/model.csv"),
        example_file=Path("models/example.csv"),
        output_file=output,
        log_dir=tmp_path / "logs",
    )

    rows = _read_csv_rows(output)
    assert rows[0]["Date"] == "2025 06 25"
    assert rows[0]["Description"] == "Transportation - Lyft"
    assert rows[0]["Amt Claimed (USD)"] == "$54.91"

    exceptions = output.with_name("Expenses_exceptions.csv")
    assert not exceptions.exists() or len(_read_csv_rows(exceptions)) == 0


def test_pipeline_flags_null_and_contradictory_results(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    (inbox / "receipt.png").write_bytes(b"not-an-image")

    contradict_receipt = inbox / "trip_2025-06-24_19.23.png"
    contradict_receipt.write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "amount: 20.00\n",
        encoding="utf-8",
    )

    output = tmp_path / "Expenses.csv"
    run_pipeline(
        input_dir=inbox,
        model_file=Path("models/model.csv"),
        example_file=Path("models/example.csv"),
        output_file=output,
        log_dir=tmp_path / "logs",
    )

    rows = _read_csv_rows(output)
    # No valid records should have been emitted.
    assert rows == []

    exceptions = _read_csv_rows(output.with_name("Expenses_exceptions.csv"))
    issue_types = {row["issue_type"] for row in exceptions}
    assert "no_relevant_information" in issue_types
    assert "contradiction_detected" in issue_types


def test_pipeline_emits_runtime_logs(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "lyft.png").write_bytes(b"not-an-image")
    (inbox / "lyft_notes.txt").write_text(
        "vendor: Lyft\ndate: 2025-06-25\namount: 54.91\nexpense_type: Transportation\n",
        encoding="utf-8",
    )

    output = tmp_path / "Expenses.csv"
    logs_dir = tmp_path / "logs"
    run_pipeline(
        input_dir=inbox,
        model_file=Path("models/model.csv"),
        example_file=Path("models/example.csv"),
        output_file=output,
        log_dir=logs_dir,
    )

    files = list(logs_dir.glob("performance-*.jsonl"))
    assert len(files) == 1

    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3
    assert any("\"event_type\": \"run_started\"" in line for line in lines)
    assert any("\"event_type\": \"receipt_processed\"" in line for line in lines)
    assert any("\"event_type\": \"run_completed\"" in line for line in lines)
