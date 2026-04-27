# src/receipt_processor/observability

Purpose:
- Structured runtime telemetry for performance evaluation and debugging.

Contents:
- `runtime_logger.py`: JSONL event logging for run-level and receipt-level performance data.

Behavior:
- Logs are written at runtime to `logs/performance-YYYY-MM-DD.jsonl`.
- Output is metadata-focused (no raw receipt text) to reduce sensitive-data exposure.
- Optional privacy mode (`RECEIPT_PROCESSOR_LOG_PRIVACY_MODE=redacted`) masks source filenames and details in log events.
- When LLM mode is enabled, logs include extraction strategy (`deterministic`, `llm`, `llm_fallback`) and non-sensitive LLM diagnostics (token usage, failure reason codes).
