# src/receipt_processor/extraction

Purpose:
- Converts receipt content into normalized expense fields.

Contents:
- `ocr_router.py`: OCR/provider abstraction.
  - For PDFs, uses embedded text first; if page text is too short it falls back to OCR on embedded page images (`RECEIPT_PROCESSOR_PDF_MIN_TEXT_CHARS`, default `60`).
- `structured_extractor.py`: deterministic structured field extraction (keywords, line items, highlight-aware contributions).
- `receipt_parser.py`: rule-based text-to-fields parsing.
- `filename_inference.py`: fallback inference from filename patterns.
- `notes_inference.py`: optional notes-file context extraction.
- `schema_mapper.py`: maps parsed fields to model columns.
