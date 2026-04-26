# Architecture

## Ownership Statement

I defined the architecture below and used Codex to scaffold and implement components after approval.

## System Flow

1. Discover supported files in `data/inbox`.
2. Route each file through OCR/text extraction.
3. Build a deterministic structured extraction object (document metadata, keyword-evidence totals, line items, contribution classification).
4. Infer missing fields from filename patterns and optional notes files.
5. Run deterministic processing to derive normalized values (`true_expense`, `receipt_expense`, summary counts/totals).
6. Infer formatting and column-role hints from `model` + `example` templates.
7. Render model-driven output rows using keyword placeholders (`{{...}}`) and operation tokens (`<...>`).
8. Score confidence and apply model-driven quality routing (null/contradiction/low-confidence review paths).
9. Enforce strict template contract checks (unknown `{{...}}` / `<...>` tokens fail export).
10. Export accepted rows, exception sidecar, and detailed JSON sidecar with spreadsheet-safe sanitization.
11. Emit structured runtime logs for run-level and receipt-level performance diagnostics.

## Layered Modules

- `io/`: file scanning, format detection, template loading, export.
- `extraction/`: OCR entrypoint, structured deterministic extraction, filename inference, schema mapping.
- `processing/`: deterministic derived-value calculations and run-level operations.
- `quality/`: confidence scoring, consistency checks, optional validation utilities, exception queue.
- `pipeline.py`: orchestration logic.
- `cli.py`: operator command interface.

## Governance Overlay

The `agent/` directory defines how Codex must operate in this repository, including risk controls, failure handling, and mandatory human approval checkpoints.
