# Architecture

## Ownership Statement

I defined the architecture below and used Codex to scaffold and implement components after approval.

## System Flow

1. Discover supported files in `data/inbox`.
2. Route each file through OCR/text extraction.
3. Parse extracted text into normalized expense fields.
4. Infer missing fields from filename patterns.
5. Infer formatting and column-role hints from `model` + `example` templates.
6. Map parsed fields onto model columns.
7. Score confidence and validate required fields.
8. Export accepted and exception records to final output format with spreadsheet-safe sanitization.
9. Emit structured runtime logs for run-level and receipt-level performance diagnostics.

## Layered Modules

- `io/`: file scanning, format detection, template loading, export.
- `extraction/`: OCR entrypoint, text parsing, filename inference, schema mapping.
- `quality/`: confidence scoring, validation, exception queue.
- `pipeline.py`: orchestration logic.
- `cli.py`: operator command interface.

## Governance Overlay

The `agent/` directory defines how Codex must operate in this repository, including risk controls, failure handling, and mandatory human approval checkpoints.
