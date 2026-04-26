from __future__ import annotations

import json
from pathlib import Path

from receipt_processor.pipeline import run_pipeline


def test_pipeline_emits_single_detailed_json_with_summary(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "lyft.png").write_bytes(b"not-an-image")
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

    details_file = output.with_name("Expenses_detailed.json")
    assert details_file.exists()

    payload = json.loads(details_file.read_text(encoding="utf-8"))
    assert "summary" in payload
    assert "receipts" in payload
    assert isinstance(payload["receipts"], list)
    assert len(payload["receipts"]) == 1
    assert payload["receipts"][0]["filename"] == "lyft.png"
    assert "processed" in payload["receipts"][0]
    assert payload["summary"]["total_expenses"] >= 0


def test_pipeline_removes_stale_exception_sidecar_when_no_current_exceptions(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    bad_receipt = inbox / "bad.png"
    bad_receipt.write_bytes(b"not-an-image")

    output = tmp_path / "Expenses.csv"
    run_pipeline(
        input_dir=inbox,
        model_file=Path("models/model.csv"),
        example_file=Path("models/example.csv"),
        output_file=output,
        log_dir=tmp_path / "logs",
    )
    exception_file = output.with_name("Expenses_exceptions.csv")
    assert exception_file.exists()

    bad_receipt.unlink()
    (inbox / "cafe.png").write_bytes(b"not-an-image")
    (inbox / "cafe_notes.txt").write_text(
        "vendor: Cafe\ndate: 2026-04-26\namount: 10.50\nexpense_type: Food\n",
        encoding="utf-8",
    )
    run_pipeline(
        input_dir=inbox,
        model_file=Path("models/model.csv"),
        example_file=Path("models/example.csv"),
        output_file=output,
        log_dir=tmp_path / "logs",
    )

    assert not exception_file.exists()
