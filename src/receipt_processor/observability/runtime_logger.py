"""Structured runtime logging for per-user performance analysis."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

USER_ID_ENV_VAR = "RECEIPT_PROCESSOR_USER_ID"
LOG_DIR_ENV_VAR = "RECEIPT_PROCESSOR_LOG_DIR"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _sanitize_user_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return normalized or "unknown_user"


def _resolve_user_id() -> str:
    explicit = os.environ.get(USER_ID_ENV_VAR, "").strip()
    if explicit:
        return _sanitize_user_id(explicit)

    try:
        import getpass

        return _sanitize_user_id(getpass.getuser())
    except Exception:
        return "unknown_user"


def _resolve_logs_root(log_dir: Path | None = None) -> Path:
    if log_dir is not None:
        return log_dir

    configured = os.environ.get(LOG_DIR_ENV_VAR, "").strip()
    if configured:
        return Path(configured)
    return Path("logs")


@dataclass
class RuntimeLogger:
    """Writes newline-delimited JSON logs partitioned by user and date."""

    log_dir: Path | None = None
    run_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = field(default_factory=_resolve_user_id)

    def _log_file_path(self) -> Path:
        root = _resolve_logs_root(self.log_dir)
        user_dir = root / "users" / self.user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now(UTC).strftime("performance-%Y-%m-%d.jsonl")
        return user_dir / filename

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Write a structured event record to the active per-user log file."""
        record = {
            "timestamp": _utc_timestamp(),
            "run_id": self.run_id,
            "user_id": self.user_id,
            "event_type": event_type,
            **payload,
        }
        log_file = self._log_file_path()
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, default=str))
            handle.write("\n")

