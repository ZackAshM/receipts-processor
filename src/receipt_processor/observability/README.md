# src/receipt_processor/observability

Purpose:
- Structured runtime telemetry for performance evaluation and debugging.

Contents:
- `runtime_logger.py`: per-user JSONL event logging for run-level and receipt-level performance data.

Behavior:
- Logs are written at runtime to `logs/users/<user_id>/performance-YYYY-MM-DD.jsonl`.
- Output is metadata-focused (no raw receipt text) to reduce sensitive-data exposure.
- Optional privacy mode (`RECEIPT_PROCESSOR_LOG_PRIVACY_MODE=redacted`) masks user IDs and source filenames in log events.
