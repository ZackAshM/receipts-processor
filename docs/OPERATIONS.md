# Operations

## Operator Runbook

1. Activate virtual environment.
2. Place source receipts in `data/inbox`.
3. Optionally add contextual notes files (`notes.txt`, `<receipt>_notes.txt`) in the same folder.
4. Choose `models/model.csv` or `models/model.xlsx`.
5. Run CLI command to generate output file.
6. Review low-confidence rows and the sidecar exception file (`*_exceptions.csv`) for null/contradiction flags.
7. Review detailed sidecar JSON (`*_detailed.json`) for extracted/processed fields, contribution itemization, and run summary totals.
8. Review runtime logs under `logs/performance-YYYY-MM-DD.jsonl` for performance/debug diagnostics.
9. Tune confidence routing in `configs/risk_controls.yaml` (or pass `--risk-controls-file`) as needed.
10. Optional: enable LLM semantic extraction via `.env` (`ENABLE_LLM=true`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `LLM_INPUT_MODE`), and optionally enable conservative LLM-first exception assist (`ENABLE_LLM_EXCEPTION_ASSIST=true`).
11. Optional: override LLM settings per run through CLI/GUI runtime controls without changing environment files.
12. CLI/GUI automatically load `.env` from the current working directory with safe precedence (existing exported env vars are not overwritten).
13. At run start, verify mode summary output (deterministic vs LLM-supported, model, and enabled flags), then monitor per-file progress lines (`<filename> [x% / 100%]`).
14. If repeated provider failures occur, the run opens an LLM circuit breaker and continues in deterministic mode for remaining files.

## Security Controls in Runtime

- Export sanitization neutralizes spreadsheet formula prefixes (`=`, `+`, `-`, `@`, tab, carriage return).
- Chat logs and governance artifacts use redaction rules for sensitive values.
- Do not place credentials in filenames, receipt images, or prompt text.
- Runtime logs intentionally avoid raw receipt text and focus on operational metadata.
- Exception sidecar exports are sanitized to prevent spreadsheet-formula execution.
- Optional runtime privacy mode can mask file-level identifiers in telemetry (`RECEIPT_PROCESSOR_LOG_PRIVACY_MODE=redacted`).
- LLM failures (if enabled) are non-fatal and automatically fall back to deterministic extraction.

## Human-in-the-Loop Controls

- No autonomous scope expansion without explicit approval.
- Exceptions must be reviewed before financial posting.
- Changes to extraction logic should update `docs/DECISIONS.md`.

## Recovery Steps

- If parsing quality degrades, inspect `data/output` and exception metadata.
- Validate model headers before each run.
- Keep original receipts unchanged in source folders.

## CODEX_LOG Redaction Script

- Use `scripts/redact_codex_log.py` after each `docs/CODEX_LOG.md` append to enforce policy redaction.
- Full-file pass (recommended periodically):
  - `.venv/bin/python scripts/redact_codex_log.py --lines 999999`
- Incremental pass after routine updates:
  - `.venv/bin/python scripts/redact_codex_log.py --lines 2000`
- Optional custom log target:
  - `.venv/bin/python scripts/redact_codex_log.py --file docs/CODEX_LOG.md --lines 2000`
