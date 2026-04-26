# Changelog

## 2026-04-25

### Added
- Created initial repository scaffold for ReceiptProcessor.
- Initialized `.venv` for isolated project runtime.
- Added package layout under `src/receipt_processor`.
- Added starter configs, tests, and data folders.
- Added product docs (`PRD`, `ARCHITECTURE`, `DECISIONS`, `OPERATIONS`).
- Added agent governance docs under `agent/`.
- Added `docs/CODEX_LOG.md` workflow integration and preserved `docs/INIT_PROMPT.txt`.

### User-Requested Adjustments
- Included and preserved `docs/INIT_PROMPT.txt` as a static initialization artifact.
- Continued `docs/CODEX_LOG.md` using the heading-and-response format the user established.
- Updated logging policy to append-only maintenance with one-response-lag updates.
- Added explicit halt-until-resume control to governance documentation.
- Redacted sensitive data in `docs/CODEX_LOG.md` (including absolute filepaths) and codified ongoing log sanitization rules.
- Added git authority guardrails: developer-only `git push`, developer-only staging of untracked files/directories, and commit creation by Codex only on explicit developer request.
- Implemented core extraction pipeline content: PDF/image text extraction, rule-based parsing, filename fallback inference, and model/example-driven schema mapping.
- Implemented spreadsheet formula-injection defenses at export time.
- Added subfolder `README.md` files to document purpose and contents across major project areas.
- Added optional notes-file ingestion (`notes.txt`, receipt-specific notes names) for extraction enrichment.
- Added null-result flagging and contradiction detection between file text, filename inference, and notes context.
- Added sidecar exception export (`*_exceptions.csv`) for flagged records.
- Added structured runtime logging in JSONL format for performance evaluation and debugging.
- Added spreadsheet sanitization for exception sidecar CSV exports.
- Enforced low-confidence routing using loaded runtime thresholds from `configs/risk_controls.yaml`.
- Added optional log privacy mode to mask file identifiers in telemetry.
- Updated runtime logging layout to write directly under `logs/` and removed `user_id` from emitted telemetry events.
- Added GitHub Actions workflows for automated CI tests and dependency vulnerability scanning.
- Added deterministic structured extraction and processing modules, including highlight-aware contribution logic for OCR image lines.
- Added model-template rendering support for `{{keyword}}` placeholders and `<operation>` summary tokens.
- Added run-level detailed sidecar export (`*_detailed.json`) containing per-receipt extracted + processed data and summary totals.
- Updated CLI UX to support direct positional invocation (`receipts_processor <input_dir>`) with optional flags.
- Changed CLI default output location to `<input_dir>/Expenses.csv` when `--output-file` is omitted.
- Added `--output-type` (`csv` default, optional `xlsx`) for output format selection.
- Added desktop GUI entrypoint with folder picker and Advanced options panel (`receipts_processor_gui`).
- Added graceful GUI startup handling for environments without `tkinter` (clear fallback guidance).

### Attribution
- Direction and requirements defined by user.
- Scaffold and implementation executed by Codex after user approval.
