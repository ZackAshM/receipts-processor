# src/receipt_processor

Purpose:
- Core package implementing receipt discovery, extraction, validation, and export.

Contents:
- `cli.py`: command-line entrypoint.
- `pipeline.py`: end-to-end orchestration.
- `io/`: file discovery, template loading, export, and sanitization.
- `extraction/`: OCR abstraction and field extraction/inference.
- `quality/`: confidence scoring, validation, and exception queue helpers.
