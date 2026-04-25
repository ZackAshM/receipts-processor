from __future__ import annotations

import json
from pathlib import Path

from receipt_processor.observability.runtime_logger import RuntimeLogger


def test_runtime_logger_writes_jsonl_events(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECEIPT_PROCESSOR_USER_ID", "dev.user")

    logger = RuntimeLogger(log_dir=tmp_path / "logs")
    logger.emit("run_started", {"input_file_count": 1})
    logger.emit("run_completed", {"processed_count": 1, "flagged_count": 0})

    user_dir = tmp_path / "logs" / "users" / "dev.user"
    files = list(user_dir.glob("performance-*.jsonl"))
    assert len(files) == 1

    records = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert records[0]["event_type"] == "run_started"
    assert records[1]["event_type"] == "run_completed"
    assert records[0]["user_id"] == "dev.user"


def test_runtime_logger_sanitizes_user_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECEIPT_PROCESSOR_USER_ID", "dev user/unsafe")

    logger = RuntimeLogger(log_dir=tmp_path / "logs")
    logger.emit("run_started", {"input_file_count": 0})

    users_dir = tmp_path / "logs" / "users"
    created_dirs = [path.name for path in users_dir.iterdir() if path.is_dir()]
    assert created_dirs == ["dev_user_unsafe"]
