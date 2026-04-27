# src/receipt_processor

Purpose:
- Core package implementing receipt discovery, extraction, model-driven quality routing, and export.

Contents:
- `cli.py`: command-line entrypoint.
- `gui.py`: desktop GUI entrypoint with folder picker and advanced options panel.
- `pipeline.py`: end-to-end orchestration.
- `io/`: file discovery, template loading, export, and sanitization.
- `extraction/`: OCR abstraction and field extraction/inference.
- `processing/`: deterministic post-extraction calculations and run-level summaries.
- `quality/`: confidence scoring, consistency checks, optional validation utilities, and exception queue helpers.
- `observability/`: structured runtime logging for performance/debugging.
- `llm/`: optional LLM semantic extraction and conservative exception-assist orchestration with deterministic/user-review fallback.
