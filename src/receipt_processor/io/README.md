# src/receipt_processor/io

Purpose:
- Input/output utilities for scanning receipts and writing safe exports.

Contents:
- `file_discovery.py`: supported input file discovery.
- `format_detector.py`: file-type normalization.
- `template_loader.py`: model schema loading from CSV/XLSX.
- `exporter.py`: export to CSV/XLSX.
- `sanitization.py`: spreadsheet injection sanitization for cell values.
