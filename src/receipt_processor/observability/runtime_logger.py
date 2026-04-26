"""Structured runtime logging for performance analysis."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LOG_DIR_ENV_VAR = "RECEIPT_PROCESSOR_LOG_DIR"
LOG_PRIVACY_MODE_ENV_VAR = "RECEIPT_PROCESSOR_LOG_PRIVACY_MODE"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_privacy_mode() -> str:
    value = os.environ.get(LOG_PRIVACY_MODE_ENV_VAR, "standard").strip().lower()
    if value in {"redacted", "strict"}:
        return "redacted"
    return "standard"


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def _resolve_logs_root(log_dir: Path | None = None) -> Path:
    if log_dir is not None:
        return log_dir

    configured = os.environ.get(LOG_DIR_ENV_VAR, "").strip()
    if configured:
        return Path(configured)
    return Path("logs")


@dataclass
class RuntimeLogger:
    """Writes newline-delimited JSON logs partitioned by date."""

    log_dir: Path | None = None
    run_id: str = field(default_factory=lambda: str(uuid4()))
    privacy_mode: str = field(default_factory=_resolve_privacy_mode)

    def _log_file_path(self) -> Path:
        root = _resolve_logs_root(self.log_dir)
        root.mkdir(parents=True, exist_ok=True)
        filename = datetime.now(UTC).strftime("performance-%Y-%m-%d.jsonl")
        return root / filename

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Write a structured event record to the active log file."""
        emitted_payload = dict(payload)

        if self.privacy_mode == "redacted":
            if "source_file" in emitted_payload:
                source_value = str(emitted_payload.pop("source_file"))
                emitted_payload["source_file_hash"] = _hash_text(source_value)
            if "matched_notes_files" in emitted_payload:
                notes_value = emitted_payload.pop("matched_notes_files")
                if isinstance(notes_value, list):
                    emitted_payload["matched_notes_count"] = len(notes_value)
                else:
                    emitted_payload["matched_notes_count"] = 0
            if "details" in emitted_payload:
                emitted_payload["details"] = "[redacted]"

        record = {
            "timestamp": _utc_timestamp(),
            "run_id": self.run_id,
            "privacy_mode": self.privacy_mode,
            "event_type": event_type,
            **emitted_payload,
        }
        log_file = self._log_file_path()
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, default=str))
            handle.write("\n")
