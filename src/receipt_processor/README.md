# src/receipt_processor

Purpose:
- Core package implementing receipt discovery, extraction, validation, and export.

Contents:
- `cli.py`: command-line entrypoint.
- `gui.py`: desktop GUI entrypoint with folder picker and advanced options panel.
- `pipeline.py`: end-to-end orchestration.
- `io/`: file discovery, template loading, export, and sanitization.
- `extraction/`: OCR abstraction and field extraction/inference.
- `quality/`: confidence scoring, validation, and exception queue helpers.
- `observability/`: structured runtime logging for performance/debugging.
