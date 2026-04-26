from __future__ import annotations

import json
from pathlib import Path

from receipt_processor.observability.runtime_logger import RuntimeLogger


def test_runtime_logger_writes_jsonl_events(tmp_path: Path) -> None:
    logger = RuntimeLogger(log_dir=tmp_path / "logs")
    logger.emit("run_started", {"input_file_count": 1})
    logger.emit("run_completed", {"processed_count": 1, "flagged_count": 0})

    files = list((tmp_path / "logs").glob("performance-*.jsonl"))
    assert len(files) == 1

    records = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert records[0]["event_type"] == "run_started"
    assert records[1]["event_type"] == "run_completed"
    assert "user_id" not in records[0]


def test_runtime_logger_writes_directly_under_log_root(tmp_path: Path) -> None:
    logger = RuntimeLogger(log_dir=tmp_path / "logs")
    logger.emit("run_started", {"input_file_count": 0})

    files = list((tmp_path / "logs").glob("performance-*.jsonl"))
    assert len(files) == 1
    assert not (tmp_path / "logs" / "users").exists()


def test_runtime_logger_redacted_mode_masks_identifiers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECEIPT_PROCESSOR_LOG_PRIVACY_MODE", "redacted")

    logger = RuntimeLogger(log_dir=tmp_path / "logs")
    logger.emit(
        "receipt_processed",
        {
            "source_file": "2025-06-25_lyft_54.91.png",
            "matched_notes_files": ["trip_notes.txt"],
            "details": "vendor mismatch",
        },
    )

    log_file = next((tmp_path / "logs").glob("performance-*.jsonl"))
    record = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])

    assert "user_id" not in record
    assert "source_file" not in record
    assert "source_file_hash" in record
    assert record["matched_notes_count"] == 1
    assert record["details"] == "[redacted]"
