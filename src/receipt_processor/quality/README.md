# src/receipt_processor/quality

Purpose:
- Quality controls and routing support for extracted records.

Contents:
- `confidence.py`: record confidence scoring.
- `validation.py`: required-field validation.
- `consistency.py`: null-result and contradiction checks across sources.
- `exception_queue.py`: exception record enrichment for manual review.
