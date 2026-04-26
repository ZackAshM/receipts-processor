# src/receipt_processor/quality

Purpose:
- Quality controls and routing support for extracted records.

Contents:
- `confidence.py`: record confidence scoring.
- `validation.py`: optional required-field validation utility (kept for tests/tooling, not a default runtime gate in the current template-driven pipeline).
- `consistency.py`: null-result and contradiction checks across sources.
- `exception_queue.py`: exception record enrichment for manual review.
